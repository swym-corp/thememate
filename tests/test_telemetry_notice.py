import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

import telemetry_common


def test_take_notice_defers_marker_until_after_display(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry_common, "STATE_DIR", tmp_path / ".thememate-telemetry")
    monkeypatch.setattr(telemetry_common, "NOTICE_MARKER", telemetry_common.STATE_DIR / "notice_shown")

    assert telemetry_common.take_notice() == telemetry_common.NOTICE
    assert not telemetry_common.NOTICE_MARKER.exists()

    telemetry_common.mark_notice_shown()

    assert telemetry_common.NOTICE_MARKER.exists()
    assert telemetry_common.take_notice() is None
