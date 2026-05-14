"""Tests for confirmed failure action helpers."""

import csv
from pathlib import Path

import numpy as np

from actions import (
    FailureEvent,
    append_event_log,
    build_event_row,
    dispatch_failure_notifications,
    get_simulated_action_name,
    handle_confirmed_failure,
    send_failure_notifications,
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


def test_handle_confirmed_failure_saves_screenshot_and_logs_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Confirmed failures should save a screenshot and log its path."""

    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    captures_dir = tmp_path / "captures"
    csv_path = tmp_path / "logs" / "events.csv"

    monkeypatch.setattr("actions.alert_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("actions.dispatch_failure_notifications", lambda event: None)
    monkeypatch.setattr(
        "actions.trigger_printer_response",
        lambda action: PrinterCommandResult(action=action, success=True, message="ok"),
    )

    event = handle_confirmed_failure(
        frame=frame,
        source="Dashboard AI: demo_video",
        label="spaghetti",
        confidence=0.93,
        printer_action="pause",
        captures_dir=captures_dir,
        events_csv_path=csv_path,
    )

    assert event.screenshot_path is not None
    assert event.screenshot_path.exists()
    assert event.screenshot_path.parent == captures_dir
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    assert rows[0]["source"] == "Dashboard AI: demo_video"
    assert rows[0]["screenshot_path"] == event.screenshot_path.as_posix()


def test_handle_confirmed_failure_continues_when_screenshot_save_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Screenshot save failures should not block action or notification dispatch."""

    calls: list[str] = []
    dispatched_events: list[FailureEvent] = []

    def fake_save(*args, **kwargs):
        calls.append("screenshot")
        raise OSError("disk full")

    def fake_printer(action):
        calls.append("printer")
        return PrinterCommandResult(action=action, success=True, message="ok")

    def fake_notify(event):
        calls.append("notify")
        dispatched_events.append(event)

    monkeypatch.setattr("actions.save_failure_screenshot", fake_save)
    monkeypatch.setattr("actions.alert_failure", lambda *args, **kwargs: None)
    monkeypatch.setattr("actions.trigger_printer_response", fake_printer)
    monkeypatch.setattr("actions.dispatch_failure_notifications", fake_notify)

    event = handle_confirmed_failure(
        frame=object(),
        source="Dashboard AI",
        label="spaghetti",
        confidence=0.91,
        printer_action="pause",
        events_csv_path=tmp_path / "logs" / "events.csv",
    )

    assert calls == ["screenshot", "printer", "notify"]
    assert event.screenshot_path is None
    assert dispatched_events[0].screenshot_path is None


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

    def fake_save(frame, timestamp, label, captures_dir=None):
        calls.append("screenshot")
        return tmp_path / "failure.jpg"

    def fake_log(event, csv_path=None):
        calls.append("csv")

    def fake_alert(source, label, confidence):
        calls.append("alert")

    def fake_notify(event):
        calls.append("notify")

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
    monkeypatch.setattr("actions.dispatch_failure_notifications", fake_notify)
    monkeypatch.setattr("actions.trigger_printer_response", fake_printer)

    from actions import handle_confirmed_failure

    event = handle_confirmed_failure(
        frame=object(),
        source="Sample video",
        label="spaghetti",
        confidence=0.91,
        printer_action="pause",
    )

    assert calls == ["screenshot", "csv", "alert", "printer", "notify"]
    assert event.action == "pause"
    assert event.action_success is True
    assert event.action_message == "ok"


def test_handle_confirmed_failure_runs_printer_when_notification_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Notification failures should not block printer response."""

    calls: list[str] = []

    def fake_save(frame, timestamp, label, captures_dir=None):
        calls.append("screenshot")
        return tmp_path / "failure.jpg"

    def fake_log(event, csv_path=None):
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
    monkeypatch.setattr("actions.dispatch_failure_notifications", fake_notify)
    monkeypatch.setattr("actions.trigger_printer_response", fake_printer)

    from actions import handle_confirmed_failure

    event = handle_confirmed_failure(
        frame=object(),
        source="Sample video",
        label="spaghetti",
        confidence=0.91,
        printer_action="stop",
    )

    assert calls == ["screenshot", "csv", "alert", "printer", "notify"]
    assert event.action_success is True


def test_dispatch_failure_notifications_runs_in_background(
    tmp_path: Path,
) -> None:
    """Notification dispatch should not run provider work inline."""

    calls: list[str] = []

    class FakeDispatcher:
        """Dispatcher stand-in that records scheduled work."""

        def dispatch(self, task) -> None:
            """Record dispatch without running provider work inline."""

            calls.append("dispatch")

    event = FailureEvent(
        timestamp="2026-04-29T12:30:01+03:00",
        source="Sample video",
        label="spaghetti",
        confidence=0.9,
        action="stop",
        screenshot_path=tmp_path / "failure.jpg",
    )

    dispatch_failure_notifications(event, dispatcher=FakeDispatcher())

    assert calls == ["dispatch"]


def test_send_failure_notifications_passes_screenshot_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Notification dispatch should pass the saved screenshot path to providers."""

    screenshot_path = tmp_path / "failure.jpg"
    captured_paths: list[Path | None] = []

    class FakeNotificationManager:
        """Notification manager stand-in that records the notification payload."""

        def __init__(self, providers):
            """Ignore configured providers."""

        def send_failure_alert(self, notification):
            """Record screenshot path and return success."""

            captured_paths.append(notification.screenshot_path)
            return [
                type(
                    "Result",
                    (),
                    {
                        "provider": "fake",
                        "destination_id": "test",
                        "success": True,
                        "message": "sent",
                    },
                )()
            ]

    monkeypatch.setattr("actions.NotificationManager", FakeNotificationManager)
    monkeypatch.setattr("actions.build_enabled_providers", lambda: ["fake"])
    monkeypatch.setattr("actions.safe_append_notification_results", lambda *args: None)

    event = FailureEvent(
        timestamp="2026-04-29T12:30:01+03:00",
        source="Dashboard AI",
        label="spaghetti",
        confidence=0.9,
        action="pause",
        screenshot_path=screenshot_path,
    )

    send_failure_notifications(event)

    assert captured_paths == [screenshot_path]
