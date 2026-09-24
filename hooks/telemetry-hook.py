#!/usr/bin/env python3
"""Emit a lifecycle telemetry event without blocking Claude Code.

Three triggers share this script:
  - UserPromptSubmit, registered in skills/thememate/SKILL.md frontmatter with
    once:true, fires session_start scoped to sessions that actually invoke ThemeMate.
  - Stop, registered in skills/thememate/SKILL.md frontmatter (not hooks.json, so it
    only fires in sessions that already loaded this skill), fires after every assistant
    turn. Sends a session_heartbeat carrying a read-only peek at whatever mode/feature/
    usecase/etc. Claude has recorded via telemetry_state.py so far, plus turns/tokens
    accumulated from the transcript so far -- skipped when no new turn showed up since
    the last Stop-triggered send, so a chatty turn with many tool calls only sends once.
    The cumulative turns/tokens plus the transcript byte offset they cover lives in its
    own `<session_id>.stopturns` file rather than in the session state JSON, because
    telemetry_state.py read-modify-writes that JSON at the end of the same turn and
    either writer can clobber the other's field. Each Stop call only (re)parses the
    transcript bytes after that cached offset instead of the whole file, so a long
    session doesn't get quadratically slower. A transcript read failure is distinct
    from a successful read finding no new turns -- it leaves the cache untouched
    rather than corrupting it with a transient glitch.
  - SessionEnd, registered in hooks/hooks.json, fires session_end as a lifecycle backstop.
    session_end also attaches whatever mode/feature/usecase/outcome Claude recorded
    via telemetry_state.py during the session, and turns/tokens parsed from the
    transcript, before the state file is deleted.

telemetry_state.py sends its own session_heartbeat events as state becomes known
mid-session too -- this script's Stop branch is a backstop for turns/tokens, which
telemetry_state.py has no way to compute (it never sees transcript_path).
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telemetry_common import (
    SESSIONS_DIR,
    SESSION_ID_RE,
    atomic_write,
    ensure_state_dir,
    install_id,
    oauth_account,
    send_event,
    skill_version,
    take_notice,
    telemetry_disabled,
)

EVENT_FOR_HOOK = {
    "UserPromptSubmit": ("session_start", "skill"),
    "Stop": ("session_heartbeat", "stop_hook"),
    "SessionEnd": ("session_end", "session_end_hook"),
}
STOP_TURNS_SUFFIX = ".stopturns"

STATE_FIELDS = (
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
TOKEN_USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens")


def seed_session_state(session_id: str, fields: dict) -> None:
    # Always write, even with no fields yet -- the file's existence is what tells
    # session_end this session actually used ThemeMate, so it must be created here
    # regardless of whether telemetry_state.py ever gets called during the session.
    fields = {k: v for k, v in fields.items() if v}
    path = SESSIONS_DIR / f"{session_id}.json"
    try:
        ensure_state_dir(path.parent)
        current = {}
        if path.exists():
            try:
                current = json.loads(path.read_text())
            except Exception:
                current = {}
        for key, value in fields.items():
            current.setdefault(key, value)
        atomic_write(path, json.dumps(current), 0o600)
    except Exception:
        pass


def session_state_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def _read_session_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    state = {k: v for k, v in data.items() if k in STATE_FIELDS and v is not None}
    if "mode" in state:
        state["mode"] = state["mode"].upper()
    return state


def consume_session_state(session_id: str) -> dict:
    path = session_state_path(session_id)
    if not path.exists():
        return {}
    state = _read_session_state(path)
    discard_session_files(session_id)
    return state


def discard_session_files(session_id: str) -> None:
    session_state_path(session_id).unlink(missing_ok=True)
    stop_progress_path(session_id).unlink(missing_ok=True)


def peek_session_state(session_id: str) -> dict:
    """Same as consume_session_state, but read-only -- only SessionEnd deletes the file."""
    path = session_state_path(session_id)
    if not path.exists():
        return {}
    return _read_session_state(path)


def stop_progress_path(session_id: str) -> Path:
    # Deliberately not the session state file: telemetry_state.py read-modify-writes
    # that one at the end of the same turn this hook fires on, and the loser of that
    # race silently drops a field Claude believes it recorded.
    return SESSIONS_DIR / f"{session_id}{STOP_TURNS_SUFFIX}"


def load_stop_progress(session_id: str) -> dict:
    """Cumulative turns/tokens already sent, the transcript byte offset they cover, and
    the assistant message ids already counted -- Claude Code can log more than one
    JSONL line per assistant message (one per content block), each repeating that
    message's full usage, so dedup by id has to survive across Stop-hook calls too."""
    try:
        data = json.loads(stop_progress_path(session_id).read_text())
        return {
            "offset": int(data["offset"]),
            "turns": int(data.get("turns", 0)),
            "tokens": int(data.get("tokens", 0)),
            "seen_ids": list(data.get("seen_ids", [])),
        }
    except Exception:
        return {"offset": 0, "turns": 0, "tokens": 0, "seen_ids": []}


def record_stop_progress(session_id: str, progress: dict) -> None:
    path = stop_progress_path(session_id)
    try:
        ensure_state_dir(path.parent)
        atomic_write(path, json.dumps(progress), 0o600)
    except Exception:
        pass


def _accumulate_transcript_line(entry: dict, acc: dict, seen_ids: set) -> None:
    entry_type = entry.get("type")
    if entry_type == "assistant":
        message = entry.get("message", {})
        mid = message.get("id")
        if mid is not None:
            if mid in seen_ids:
                return  # duplicate content-block line for an already-counted message
            seen_ids.add(mid)
        usage = message.get("usage") or {}
        acc["tokens"] += sum(usage.get(key) or 0 for key in TOKEN_USAGE_KEYS)
    elif entry_type == "user":
        content = entry.get("message", {}).get("content")
        if isinstance(content, str):
            acc["turns"] += 1
        elif isinstance(content, list) and not all(
            isinstance(block, dict) and block.get("type") == "tool_result" for block in content
        ):
            acc["turns"] += 1


def transcript_stats(transcript_path: str | None) -> dict:
    """One-shot full parse, used only by session_end (runs once, no offset to reuse)."""
    if not transcript_path:
        return {}
    acc = {"turns": 0, "tokens": 0}
    seen_ids: set = set()
    try:
        with open(transcript_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                _accumulate_transcript_line(entry, acc, seen_ids)
    except Exception:
        return {}
    stats = {}
    if acc["turns"]:
        stats["turns"] = acc["turns"]
    if acc["tokens"]:
        stats["tokens"] = acc["tokens"]
    return stats


def transcript_progress(transcript_path: str | None, offset: int, seen_ids: set) -> tuple[dict, int] | None:
    """Parse only the transcript bytes after `offset`. None means the read failed --
    distinct from a successful read that found zero new turns -- so callers can leave
    the cached offset untouched instead of corrupting it with a transient glitch."""
    if not transcript_path:
        return None
    try:
        with open(transcript_path, "rb") as fh:
            fh.seek(offset)
            data = fh.read()
    except Exception:
        return None
    if not data:
        return {"turns": 0, "tokens": 0}, offset
    if data.endswith(b"\n"):
        new_offset = offset + len(data)
    else:
        # Trailing partial line -- still being written. Only count whole lines and
        # leave the rest for next time so we never parse a half-written entry.
        last_newline = data.rfind(b"\n")
        if last_newline == -1:
            return {"turns": 0, "tokens": 0}, offset
        data = data[: last_newline + 1]
        new_offset = offset + last_newline + 1
    acc = {"turns": 0, "tokens": 0}
    for line in data.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        _accumulate_transcript_line(entry, acc, seen_ids)
    return acc, new_offset


def main() -> int:
    try:
        hook = json.loads(sys.stdin.read() or "{}")
        session_id = hook.get("session_id")
        if not session_id or not SESSION_ID_RE.fullmatch(session_id):
            return 0
        if telemetry_disabled():
            if hook.get("hook_event_name") == "SessionEnd":
                discard_session_files(session_id)
            return 0
        mapping = EVENT_FOR_HOOK.get(hook.get("hook_event_name"))
        if mapping is None:
            return 0
        event_type, source = mapping
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "install_id": install_id(),
            "session_id": session_id,
            "skill": "thememate",
            "skill_version": skill_version(),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "schema_version": 1,
        }
        if event_type == "session_start":
            seed_session_state(session_id, {"agency_name": oauth_account().get("organizationName")})
        if hook.get("hook_event_name") == "Stop":
            notice = take_notice()
            if notice:
                print(json.dumps({"systemMessage": notice}))
            if not session_state_path(payload["session_id"]).exists():
                return 0
            progress = load_stop_progress(payload["session_id"])
            seen_ids = set(progress["seen_ids"])
            result = transcript_progress(hook.get("transcript_path"), progress["offset"], seen_ids)
            if result is None:
                return 0  # transient read failure -- skip this turn, don't touch the cache
            delta, new_offset = result
            new_progress = {
                "offset": new_offset,
                "turns": progress["turns"] + delta["turns"],
                "tokens": progress["tokens"] + delta["tokens"],
                "seen_ids": list(seen_ids),
            }
            record_stop_progress(payload["session_id"], new_progress)
            if delta["turns"] == 0:
                return 0  # no new turn since the last heartbeat -- skip
            payload.update(peek_session_state(payload["session_id"]))
            if new_progress["turns"]:
                payload["turns"] = new_progress["turns"]
            if new_progress["tokens"]:
                payload["tokens"] = new_progress["tokens"]
        if event_type == "session_end":
            if not session_state_path(payload["session_id"]).exists():
                return 0
            payload.update(consume_session_state(payload["session_id"]))
            payload.update(transcript_stats(hook.get("transcript_path")))
        send_event(payload, hook.get("cwd"))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
