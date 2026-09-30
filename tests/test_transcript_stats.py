import importlib.util
import json
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
_spec = importlib.util.spec_from_file_location("telemetry_hook", HOOKS / "telemetry-hook.py")
telemetry_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(telemetry_hook)


def prompt(ts, text="hi"):
    return {"type": "user", "timestamp": ts, "message": {"content": text}}


def skill_text(ts):
    return {"type": "user", "isMeta": True, "timestamp": ts, "message": {"content": [{"type": "text", "text": "Base directory for this skill: /x"}]}}


def tool_result(ts):
    return {"type": "user", "timestamp": ts, "message": {"content": [{"type": "tool_result", "content": "ok"}]}}


def reply(ts, mid, tokens=10):
    return {"type": "assistant", "timestamp": ts, "message": {"id": mid, "usage": {"input_tokens": tokens}}}


def tool_call(ts, mid, name, tool_id):
    return {"type": "assistant", "timestamp": ts, "message": {"id": mid, "content": [{"type": "tool_use", "id": tool_id, "name": name}]}}


def answer(ts, tool_id):
    return {"type": "user", "timestamp": ts, "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}]}}


def interrupt(ts, text="[Request interrupted by user]"):
    return {"type": "user", "timestamp": ts, "message": {"content": [{"type": "text", "text": text}]}}


def write(path, entries):
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))


def test_skill_text_and_tool_results_are_not_turns(tmp_path):
    t = tmp_path / "t.jsonl"
    write(t, [
        prompt("2026-09-30T10:00:00Z", "/swym:thememate what is fetchLists"),
        skill_text("2026-09-30T10:00:00Z"),
        reply("2026-09-30T10:00:05Z", "m1"),
        tool_result("2026-09-30T10:00:06Z"),
        reply("2026-09-30T10:00:10Z", "m2"),
    ])
    assert telemetry_hook.transcript_stats(str(t))["turns"] == 1


def test_active_time_excludes_the_wait_before_each_prompt(tmp_path):
    t = tmp_path / "t.jsonl"
    write(t, [
        prompt("2026-09-30T10:00:00Z"),
        reply("2026-09-30T10:01:00Z", "m1"),  # 1 min of work
        prompt("2026-09-30T10:40:00Z"),       # 39 min of the person being away
        reply("2026-09-30T10:40:30Z", "m2"),  # 0.5 min of work
    ])
    stats = telemetry_hook.transcript_stats(str(t))
    assert stats["turns"] == 2
    assert stats["active_minutes"] == 1.5


def test_repeated_message_lines_count_tokens_once_but_still_advance_time(tmp_path):
    t = tmp_path / "t.jsonl"
    write(t, [
        prompt("2026-09-30T10:00:00Z"),
        reply("2026-09-30T10:00:30Z", "m1", tokens=100),
        reply("2026-09-30T10:01:00Z", "m1", tokens=100),
    ])
    stats = telemetry_hook.transcript_stats(str(t))
    assert stats["tokens"] == 100
    assert stats["active_minutes"] == 1.0


def test_incremental_parse_matches_full_parse_across_a_split_turn(tmp_path):
    entries = [
        prompt("2026-09-30T10:00:00Z"),
        skill_text("2026-09-30T10:00:00Z"),
        reply("2026-09-30T10:00:30Z", "m1"),
        tool_result("2026-09-30T10:01:00Z"),
        reply("2026-09-30T10:02:00Z", "m2"),
        prompt("2026-09-30T10:30:00Z"),
        reply("2026-09-30T10:31:00Z", "m3"),
        tool_call("2026-09-30T10:31:10Z", "m4", "AskUserQuestion", "q1"),
        answer("2026-09-30T11:00:00Z", "q1"),
        reply("2026-09-30T11:00:30Z", "m5"),
        interrupt("2026-09-30T11:01:00Z"),
    ]
    t = tmp_path / "t.jsonl"
    write(t, entries)
    full = telemetry_hook.transcript_stats(str(t))

    offset, seen, last_ts = 0, set(), None
    turns = tokens = 0
    active = 0.0
    for end in (3, 4, 9, len(entries)):  # the split at 3 lands inside the first turn
        write(t, entries[:end])
        delta, offset = telemetry_hook.transcript_progress(str(t), offset, seen, last_ts)
        turns += delta["turns"]
        tokens += delta["tokens"]
        active += delta["active_seconds"]
        last_ts = delta["last_ts"]

    assert (turns, tokens, round(active / 60, 1)) == (full["turns"], full["tokens"], full["active_minutes"])
    assert full["active_minutes"] == 4.2


def test_wait_on_a_question_is_not_active_time(tmp_path):
    t = tmp_path / "t.jsonl"
    write(t, [
        prompt("2026-09-30T10:00:00Z"),
        tool_call("2026-09-30T10:00:30Z", "m1", "AskUserQuestion", "q1"),  # 0.5 min of work
        tool_call("2026-09-30T10:00:30Z", "m1", "Bash", "b1"),             # same message, second block
        answer("2026-09-30T10:08:00Z", "q1"),                              # 7.5 min of the person choosing
        answer("2026-09-30T10:08:30Z", "b1"),                              # 0.5 min of the tool running
        reply("2026-09-30T10:09:30Z", "m2"),                               # 1 min of work
    ])
    assert telemetry_hook.transcript_stats(str(t))["active_minutes"] == 2.0


def test_each_gap_is_capped(tmp_path):
    t = tmp_path / "t.jsonl"
    write(t, [
        prompt("2026-09-30T10:00:00Z"),
        tool_call("2026-09-30T10:01:00Z", "m1", "Bash", "b1"),  # 1 min of work
        answer("2026-09-30T13:00:00Z", "b1"),                   # permission prompt left open 3 h
    ])
    assert telemetry_hook.transcript_stats(str(t))["active_minutes"] == 11.0


def test_interrupts_are_not_turns_and_the_work_before_them_counts(tmp_path):
    t = tmp_path / "t.jsonl"
    write(t, [
        prompt("2026-09-30T10:00:00Z"),
        tool_call("2026-09-30T10:01:00Z", "m1", "Bash", "b1"),                          # 1 min
        interrupt("2026-09-30T10:03:00Z", "[Request interrupted by user for tool use]"),  # 2 min
        prompt("2026-09-30T10:20:00Z"),
        reply("2026-09-30T10:21:00Z", "m2"),                                            # 1 min
        interrupt("2026-09-30T10:22:00Z"),                                              # 1 min
    ])
    stats = telemetry_hook.transcript_stats(str(t))
    assert stats["turns"] == 2
    assert stats["active_minutes"] == 5.0
