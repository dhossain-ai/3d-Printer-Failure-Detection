"""Tests for confirmed failure action helpers."""

from pathlib import Path

from actions import FailureEvent, append_event_log, build_event_row, get_simulated_action_name


def test_build_event_row_formats_confidence_and_path() -> None:
    """CSV rows should have stable string values."""

    event = FailureEvent(
        timestamp="2026-04-29T12:30:01+03:00",
        source="Sample video",
        label="spaghetti",
        confidence=0.91234,
        action="stop",
        screenshot_path=Path("captures/failure.jpg"),
    )

    assert build_event_row(event) == {
        "timestamp": "2026-04-29T12:30:01+03:00",
        "source": "Sample video",
        "label": "spaghetti",
        "confidence": "0.9123",
        "action": "stop",
        "screenshot_path": "captures/failure.jpg",
    }


def test_append_event_log_writes_header_and_row(tmp_path: Path) -> None:
    """Event logging should create a CSV file if it does not exist."""

    event = FailureEvent(
        timestamp="2026-04-29T12:30:01+03:00",
        source="Webcam 0",
        label="zits",
        confidence=0.8,
        action="pause",
        screenshot_path=tmp_path / "capture.jpg",
    )
    csv_path = tmp_path / "logs" / "events.csv"

    append_event_log(event, csv_path=csv_path)

    content = csv_path.read_text(encoding="utf-8")
    assert "timestamp,source,label,confidence,action,screenshot_path" in content
    assert "Webcam 0,zits,0.8000,pause" in content


def test_get_simulated_action_name_defaults_to_stop() -> None:
    """Unsupported simulated actions should safely resolve to stop."""

    assert get_simulated_action_name("pause") == "pause"
    assert get_simulated_action_name(" PAUSE ") == "pause"
    assert get_simulated_action_name("stop") == "stop"
    assert get_simulated_action_name("shutdown") == "stop"
