"""Tests for confirmed failure action helpers."""

from pathlib import Path

from actions import (
    FailureEvent,
    append_event_log,
    build_event_row,
    get_simulated_action_name,
    trigger_printer_response,
)
from printer_controller import PrinterCommandResult


class FailingController:
    """Controller stub that fails health and action requests."""

    def stop_print(self) -> PrinterCommandResult:
        """Return a failed stop result."""

        return PrinterCommandResult(
            action="stop",
            success=False,
            message="stop failed",
        )

    def pause_print(self) -> PrinterCommandResult:
        """Return a failed pause result."""

        return PrinterCommandResult(
            action="pause",
            success=False,
            message="pause failed",
        )

    def healthcheck(self) -> PrinterCommandResult:
        """Return a failed healthcheck result."""

        return PrinterCommandResult(
            action="healthcheck",
            success=False,
            message="health failed",
        )


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


def test_trigger_printer_response_warns_without_raising(capsys) -> None:
    """Printer control failures should be reported without crashing."""

    result = trigger_printer_response("stop", controller=FailingController())

    captured = capsys.readouterr()
    assert not result.success
    assert "health failed" in captured.err
    assert "stop failed" in captured.err


def test_handle_confirmed_failure_runs_all_response_steps(monkeypatch, tmp_path: Path) -> None:
    """Confirmed failure handling should save, log, alert, and control printer."""

    calls: list[str] = []

    def fake_save(frame, timestamp, label):
        calls.append("screenshot")
        return tmp_path / "failure.jpg"

    def fake_log(event):
        calls.append("csv")

    def fake_alert(source, label, confidence):
        calls.append("alert")

    def fake_notify(event):
        calls.append("notify")
        return []

    def fake_printer(action):
        calls.append("printer")
        return PrinterCommandResult(
            action=action,
            success=True,
            message="ok",
        )

    monkeypatch.setattr("actions.save_failure_screenshot", fake_save)
    monkeypatch.setattr("actions.append_event_log", fake_log)
    monkeypatch.setattr("actions.alert_failure", fake_alert)
    monkeypatch.setattr("actions.send_failure_notifications", fake_notify)
    monkeypatch.setattr("actions.trigger_printer_response", fake_printer)

    from actions import handle_confirmed_failure

    event = handle_confirmed_failure(
        frame=object(),
        source="Sample video",
        label="spaghetti",
        confidence=0.91,
        printer_action="pause",
    )

    assert calls == ["screenshot", "csv", "alert", "notify", "printer"]
    assert event.action == "pause"
    assert event.action_success is True
    assert event.action_message == "ok"


def test_handle_confirmed_failure_runs_printer_when_notification_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Notification failures should not block printer response."""

    calls: list[str] = []

    def fake_save(frame, timestamp, label):
        calls.append("screenshot")
        return tmp_path / "failure.jpg"

    def fake_log(event):
        calls.append("csv")

    def fake_alert(source, label, confidence):
        calls.append("alert")

    def fake_notify(event):
        calls.append("notify")
        raise RuntimeError("notification failed")

    def fake_printer(action):
        calls.append("printer")
        return PrinterCommandResult(
            action=action,
            success=True,
            message="ok",
        )

    monkeypatch.setattr("actions.save_failure_screenshot", fake_save)
    monkeypatch.setattr("actions.append_event_log", fake_log)
    monkeypatch.setattr("actions.alert_failure", fake_alert)
    monkeypatch.setattr("actions.send_failure_notifications", fake_notify)
    monkeypatch.setattr("actions.trigger_printer_response", fake_printer)

    from actions import handle_confirmed_failure

    event = handle_confirmed_failure(
        frame=object(),
        source="Sample video",
        label="spaghetti",
        confidence=0.91,
        printer_action="stop",
    )

    assert calls == ["screenshot", "csv", "alert", "notify", "printer"]
    assert event.action_success is True
