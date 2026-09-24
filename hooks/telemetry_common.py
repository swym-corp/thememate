#!/usr/bin/env python3
"""Shared state-dir, identity, and send helpers for the ThemeMate telemetry hooks.

Used by both telemetry-hook.py (session_start/session_end) and telemetry_state.py
(session_heartbeat), so the kill switch, anonymous mode, and file permissions
behave identically no matter which script is sending.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

ENDPOINT = "https://swym-thememate-telemetry.internalswym.com/v1/telemetry/events"
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]+")
STATE_DIR = Path.home() / ".claude" / ".thememate-telemetry"
SESSIONS_DIR = STATE_DIR / "sessions"
INSTALL_ID_FILE = STATE_DIR / "install_id"
ANON_INSTALL_ID_FILE = STATE_DIR / "install_id_anonymous"
NOTICE_MARKER = STATE_DIR / "notice_shown"
PROFILE_FILE = Path.home() / ".claude" / ".thememate" / "profile.json"
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parent.parent))
SKILL_MANIFEST = PLUGIN_ROOT / "skills" / "thememate" / "SKILL.md"
ACCOUNT_FILE = Path.home() / ".claude.json"
TEAMS = ("acq", "success", "support", "other")

NOTICE = (
    "ThemeMate sends usage telemetry to Swym, including your email address and name. "
    "Set THEMEMATE_TELEMETRY_ANONYMOUS=1 to leave out your email and name, or "
    "THEMEMATE_TELEMETRY_DISABLED=1 to turn telemetry off entirely. To keep either "
    "setting, add it under \"env\" in ~/.claude/settings.json. See the plugin README "
    "for exactly what is sent."
)

SEND_SNIPPET = (
    "import sys,urllib.request\n"
    "req=urllib.request.Request(sys.argv[1], data=sys.stdin.buffer.read(), "
    "headers={'Content-Type':'application/json'}, method='POST')\n"
    "try:\n"
    "    urllib.request.urlopen(req, timeout=3)\n"
    "except Exception:\n"
    "    pass\n"
)


def telemetry_disabled() -> bool:
    return bool(os.environ.get("THEMEMATE_TELEMETRY_DISABLED"))


def telemetry_anonymous() -> bool:
    return bool(os.environ.get("THEMEMATE_TELEMETRY_ANONYMOUS"))


def ensure_state_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except Exception:
        pass


def atomic_write(path: Path, data: str, mode: int) -> None:
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(data)
    tmp.chmod(mode)
    os.replace(tmp, path)


def install_id() -> str:
    """Anonymous mode keeps its own install id: the server attaches every email it has
    seen to the install record, so reusing an identified install id would link
    anonymous sessions back to that email."""
    path = ANON_INSTALL_ID_FILE if telemetry_anonymous() else INSTALL_ID_FILE
    ensure_state_dir(STATE_DIR)
    if not path.exists():
        path.write_text(str(uuid.uuid4()))
        path.chmod(0o600)
    return path.read_text().strip()


def skill_version() -> str:
    try:
        frontmatter = SKILL_MANIFEST.read_text().split("---")[1]
        match = re.search(r"^\s*version:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
        return match.group(1) if match else "unknown"
    except Exception:
        return "unknown"


def oauth_account() -> dict:
    try:
        return json.loads(ACCOUNT_FILE.read_text()).get("oauthAccount") or {}
    except Exception:
        return {}


def git_config(cwd: str | None, key: str) -> str | None:
    if not cwd:
        return None
    try:
        result = subprocess.run(["git", "-C", cwd, "config", key], capture_output=True, text=True, timeout=2)
        return result.stdout.strip() or None
    except Exception:
        return None


def identity(cwd: str | None) -> dict:
    account = oauth_account()
    return {
        "email": account.get("emailAddress") or git_config(cwd, "user.email"),
        "name": account.get("fullName") or account.get("displayName") or git_config(cwd, "user.name"),
    }


def read_profile() -> dict:
    try:
        return json.loads(PROFILE_FILE.read_text())
    except Exception:
        return {}


def write_profile(profile: dict) -> None:
    ensure_state_dir(PROFILE_FILE.parent)
    atomic_write(PROFILE_FILE, json.dumps(profile), 0o600)


def take_notice() -> str | None:
    """The first-use telemetry notice, returned once per machine and never again."""
    if NOTICE_MARKER.exists():
        return None
    try:
        ensure_state_dir(STATE_DIR)
        NOTICE_MARKER.write_text("")
    except Exception:
        return None
    return NOTICE


def send_event(payload: dict, cwd: str | None = None) -> None:
    """Fire-and-forget POST, honoring the kill switch and anonymous mode.

    Every event carries email/name, not only session_start: that one fires from a
    once:true UserPromptSubmit hook that never runs when ThemeMate loads on a session's
    last prompt, which left whole sessions with no identity on the dashboard. The
    payload goes to the child on stdin so it never appears in the process list.
    """
    if telemetry_disabled():
        return
    if telemetry_anonymous():
        payload.pop("email", None)
        payload.pop("name", None)
    else:
        ident = identity(cwd or os.getcwd())
        for key in ("email", "name"):
            if ident.get(key) and not payload.get(key):
                payload[key] = ident[key]
    if payload.get("role") != "agency":
        payload.pop("agency_name", None)
    team = read_profile().get("team")
    if payload.get("role") == "swym_internal" and team in TEAMS:
        payload["team"] = team
    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", SEND_SNIPPET, ENDPOINT],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        proc.stdin.write(json.dumps(payload).encode())
        proc.stdin.close()
    except Exception:
        pass
