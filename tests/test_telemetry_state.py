import importlib.util
import json
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))

import telemetry_state

SESSION_ID = "11111111-2222-3333-4444-555555555555"


def load_hook():
    spec = importlib.util.spec_from_file_location("telemetry_hook", HOOKS / "telemetry-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sent(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(telemetry_state, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(telemetry_state, "send_event", events.append)
    monkeypatch.setattr(telemetry_state, "oauth_account", lambda: {})
    monkeypatch.setattr(telemetry_state, "install_id", lambda: "install")
    monkeypatch.setattr(telemetry_state, "telemetry_disabled", lambda: False)
    return events


def run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["telemetry_state.py", *args, "--session-id", SESSION_ID])
    return telemetry_state.main()


def stored(tmp_path):
    return json.loads((tmp_path / "sessions" / f"{SESSION_ID}.json").read_text())


def test_hook_forwards_every_state_field():
    # session_end forwards only STATE_FIELDS, so a field missing there never reaches it.
    assert tuple(load_hook().STATE_FIELDS) == tuple(telemetry_state.FIELDS)


def test_feedback_is_stored_and_sent_on_heartbeat(tmp_path, monkeypatch, sent):
    run(monkeypatch, "set", "--satisfaction", "negative", "--feedback-note", "Missed a bug")

    assert stored(tmp_path)["satisfaction"] == "negative"
    assert sent[-1]["event_type"] == "session_heartbeat"
    assert sent[-1]["session_id"] == SESSION_ID
    assert sent[-1]["satisfaction"] == "negative"
    assert sent[-1]["feedback_note"] == "Missed a bug"


def test_rating_without_note_is_sent(tmp_path, monkeypatch, sent):
    run(monkeypatch, "set", "--satisfaction", "positive")

    assert sent[-1]["satisfaction"] == "positive"
    assert "feedback_note" not in sent[-1]


def test_unknown_rating_is_refused(monkeypatch, sent):
    with pytest.raises(SystemExit):
        run(monkeypatch, "set", "--satisfaction", "good")
    assert sent == []


def test_feedback_note_is_trimmed_to_server_limit(tmp_path, monkeypatch, sent):
    run(monkeypatch, "set", "--satisfaction", "negative", "--feedback-note", "é" * 300)

    assert len(sent[-1]["feedback_note"].encode("utf-8")) <= 400


def test_new_usecase_drops_previous_feedback(tmp_path, monkeypatch, sent):
    run(monkeypatch, "set", "--usecase", "first ask", "--satisfaction", "neutral", "--feedback-note", "ok")
    run(monkeypatch, "set", "--usecase", "second ask")

    state = stored(tmp_path)
    assert "satisfaction" not in state
    assert "feedback_note" not in state
    assert "satisfaction" not in sent[-1]
