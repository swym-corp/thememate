#!/usr/bin/env python3
"""Record in-session ThemeMate telemetry (mode/feature/usecase/outcome).

Called by Claude during a ThemeMate session (see skills/thememate/SKILL.md)
whenever mode/feature/usecase becomes known or the task reaches a stopping
point. Writes to a per-session state file that telemetry-hook.py reads and
attaches to the session_end event, then deletes.

`get` reads that same state file back (read-only, no heartbeat) so the skill
can check what's already recorded -- e.g. the current usecase -- before
deciding whether a new `set` should overwrite it. `summary` overwrites like
every other field -- the skill is expected to send a fresh, self-contained
restatement of the whole session so far on each call, not a delta, since
there's no code-side accumulation, and is expected to already be short (see
telemetry.md). The 400-byte cap here is a last-resort safety net for that,
not the primary mechanism -- the telemetry server rejects the entire event
outright if `summary` runs longer, so a truncated-but-accepted event beats a
dropped one. The cap is applied to the UTF-8 byte length, matching the
server's own limit, not the character count.

A `--usecase` that differs from the one already on record means the user
pivoted to a materially different ask (see telemetry.md) -- that starts a
fresh outcome lifecycle, so `outcome`/`usecase_met`/`failure_category`/
`estimated_human_minutes` from the prior usecase are dropped rather than
carried over.

Also sends a session_heartbeat event with whatever state is known so far --
mode/feature/usecase/outcome would otherwise only ever reach the server at
session_end, which for a long-running session may not happen for a while (or,
mid-conversation, at all). The heartbeat carries the same session_id as the
session_start/session_end events so the server merges it into that one
session document instead of creating a separate row.

`get-profile` / `set-profile --team` read and write the Swym internal team, saved
once per machine outside the telemetry state so the skill asks it only once. It is
kept even when telemetry is disabled, since it is the skill's memory of an answer
and nothing about it is sent unless telemetry is on.

`change-id` prints a fresh id for one marked theme change (`c` + 8 hex digits, from
`secrets`, never invented by the model, since invented "random" hex repeats), or prints
nothing when telemetry is off so the skill stamps no id at all. `change` reports one such
change the moment it is pushed or handed off, as its own `change` event, so the telemetry
server's daily crawler can check the storefront for that marker. It applies the server's
own rules before sending (a `.myshopify.com` store, a bare page path, theme-relative files,
a theme id exactly when delivery is push), because the server rejects a malformed event
whole and this script never reads the response.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telemetry_common import (
    SESSIONS_DIR,
    SESSION_ID_RE,
    TEAMS,
    atomic_write,
    install_id,
    oauth_account,
    read_profile,
    send_event,
    skill_version,
    telemetry_disabled,
    write_profile,
)

FIELDS = (
    "mode",
    "feature",
    "usecase",
    "usecase_met",
    "outcome",
    "failure_category",
    "summary",
    "role",
    "agency_name",
    "merchant_store_url",
    "demo_store_url",
    "estimated_human_minutes",
)


CHANGE_ID_RE = re.compile(r"c[0-9a-f]{8}")
STORE_HANDLE_RE = re.compile(r"[a-z0-9][a-z0-9-]*\.myshopify\.com")
THEME_FILE_RE = re.compile(r"(assets|blocks|config|layout|locales|sections|snippets|templates)/[A-Za-z0-9._/-]+")


def state_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def build_heartbeat(session_id: str, state: dict) -> dict:
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "session_heartbeat",
        "install_id": install_id(),
        "session_id": session_id,
        "skill": "thememate",
        "skill_version": skill_version(),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "skill",
        "schema_version": 1,
    }
    for field in FIELDS:
        value = state.get(field)
        if value is None:
            continue
        payload[field] = value.upper() if field == "mode" else value
    return payload


def build_change(session_id: str, state: dict, args: argparse.Namespace) -> dict | None:
    """The change event, or None when any field would make the server refuse it."""
    store = (args.merchant_store_url or "").strip().lower()
    page = args.page or ""
    files = [path.strip() for path in (args.files or "").split(",") if path.strip()]
    if not (args.change_id and CHANGE_ID_RE.fullmatch(args.change_id)):
        return None
    if not STORE_HANDLE_RE.fullmatch(store):
        return None
    if not page.startswith("/") or page.startswith("//") or len(page) > 512:
        return None
    if any(char in "?#\\" or ord(char) <= 32 for char in page):
        return None
    if len(files) > 20 or any(len(path) > 256 or ".." in path or not THEME_FILE_RE.fullmatch(path) for path in files):
        return None
    if args.delivery not in ("push", "handoff"):
        return None
    if (args.delivery == "push") != (args.theme_id is not None):
        return None
    payload = {
        "event_id": str(uuid.uuid4()),
        "event_type": "change",
        "install_id": install_id(),
        "session_id": session_id,
        "skill": "thememate",
        "skill_version": skill_version(),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "skill",
        "schema_version": 1,
        "change_id": args.change_id,
        "store": store,
        "page_path": page,
        "delivery": args.delivery,
        "markable": not args.unmarkable,
        "files": files,
    }
    if args.theme_id is not None:
        payload["pushed_theme_id"] = args.theme_id
    for field in ("feature", "role"):
        if state.get(field):
            payload[field] = state[field]
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["set", "get", "get-profile", "set-profile", "change-id", "change"])
    parser.add_argument("--session-id", default=os.environ.get("CLAUDE_CODE_SESSION_ID"))
    parser.add_argument("--mode", choices=["ask", "inspect", "edit"])
    parser.add_argument("--feature", choices=["Wishlist Plus", "Save For Later", "Back In Stock", "Recently Viewed", "B2B List", "Gift Registry", "Recommendations", "Smart Save", "Other"])
    parser.add_argument("--usecase")
    parser.add_argument("--usecase-met", dest="usecase_met", choices=["yes", "no"])
    parser.add_argument("--outcome", choices=["completed", "blocked", "error", "scope_rejected"])
    parser.add_argument("--failure-category", dest="failure_category")
    parser.add_argument("--summary")
    parser.add_argument("--role", choices=["agency", "merchant", "swym_internal"])
    parser.add_argument("--team", choices=TEAMS)
    parser.add_argument("--store", dest="merchant_store_url")
    parser.add_argument("--demo-store", dest="demo_store_url")
    parser.add_argument("--human-minutes", dest="estimated_human_minutes", type=float)
    parser.add_argument("--id", dest="change_id")
    parser.add_argument("--page")
    parser.add_argument("--delivery", choices=["push", "handoff"])
    parser.add_argument("--theme-id", dest="theme_id", type=int)
    parser.add_argument("--files")
    parser.add_argument("--unmarkable", action="store_true")
    args = parser.parse_args()

    if args.action == "get-profile":
        print(json.dumps(read_profile()))
        return 0
    if args.action == "set-profile":
        if args.team:
            try:
                write_profile({**read_profile(), "team": args.team})
            except Exception:
                pass
        return 0
    if telemetry_disabled():
        return 0
    if args.action == "change-id":
        print(f"c{secrets.token_hex(4)}")
        return 0

    # Called silently by the skill mid-session (see SKILL.md) -- never print or
    # exit non-zero for a missing/invalid session id, just no-op.
    if not args.session_id or not SESSION_ID_RE.fullmatch(args.session_id):
        return 0

    if args.action == "change":
        try:
            path = state_path(args.session_id)
            current = json.loads(path.read_text()) if path.exists() else {}
        except Exception:
            current = {}
        payload = build_change(args.session_id, current, args)
        if payload is not None:
            send_event(payload)
        return 0

    if args.action == "get":
        # Read-only: lets the skill check what's already recorded (e.g. the
        # current usecase) before deciding whether to overwrite it. No
        # heartbeat is sent -- this doesn't change any state.
        path = state_path(args.session_id)
        try:
            current = json.loads(path.read_text()) if path.exists() else {}
        except Exception:
            current = {}
        print(json.dumps({field: current[field] for field in FIELDS if field in current}))
        return 0

    try:
        path = state_path(args.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        path.parent.parent.chmod(0o700)
        current = {}
        if path.exists():
            try:
                current = json.loads(path.read_text())
            except Exception:
                current = {}
        org = oauth_account().get("organizationName")
        if org and not current.get("agency_name"):
            current["agency_name"] = org
        if args.usecase is not None and current.get("usecase") not in (None, args.usecase):
            current.pop("outcome", None)
            current.pop("usecase_met", None)
            current.pop("failure_category", None)
            current.pop("estimated_human_minutes", None)
        for field in FIELDS:
            value = getattr(args, field, None)
            if value is None:
                continue
            if field == "summary":
                value = value.encode("utf-8")[:400].decode("utf-8", errors="ignore")
            current[field] = value
        atomic_write(path, json.dumps(current), 0o600)
    except Exception:
        return 0

    send_event(build_heartbeat(args.session_id, current))
    return 0


if __name__ == "__main__":
    sys.exit(main())
