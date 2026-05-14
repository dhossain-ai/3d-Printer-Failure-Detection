"""Failure response actions for PrintSentinel."""

import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    ALERT_BEEP_ENABLED,
    CAPTURES_DIR,
    EVENTS_CSV_PATH,
    LOGS_DIR,
    PRINTER_ACTION,
)
from notifications.dispatcher import NotificationDispatcher
from notifications.logging import safe_append_notification_results
from notifications.manager import NotificationManager, build_enabled_providers
from notifications.models import FailureNotification, NotificationResult
from printer_controller import (
    PrinterCommandResult,
    PrinterController,
    SimulatedPrinterController,
    create_printer_controller,
    execute_printer_action,
    normalize_printer_action,
)
from utils import now_local, safe_filename_part, safe_timestamp

CSV_COLUMNS = (
    "timestamp",
    "source",
    "label",
    "confidence",
    "action",
    "screenshot_path",
)

_NOTIFICATION_DISPATCHER = NotificationDispatcher()


@dataclass(frozen=True)
class FailureEvent:
    """Recorded response for a confirmed print failure."""

    timestamp: str
    source: str
    label: str
    confidence: float
    action: str
    screenshot_path: Path | None
    action_success: bool | None = None
    action_message: str | None = None


def ensure_action_paths() -> None:
    """Create captures and logs directories if they are missing."""

    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def save_failure_screenshot(
    frame: Any,
    timestamp: datetime,
    label: str,
    captures_dir: Path = CAPTURES_DIR,
) -> Path:
    """Save a failure screenshot and return the written path."""

    captures_dir.mkdir(parents=True, exist_ok=True)
    filename = f"failure_{safe_timestamp(timestamp)}_{safe_filename_part(label)}.jpg"
    screenshot_path = captures_dir / filename

    import cv2

    if not cv2.imwrite(str(screenshot_path), frame):
        raise RuntimeError(f"Could not save failure screenshot: {screenshot_path}")

    return screenshot_path


def append_event_log(event: FailureEvent, csv_path: Path = EVENTS_CSV_PATH) -> None:
    """Append a confirmed failure event to the CSV log."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        if should_write_header:
            writer.writeheader()

        writer.writerow(build_event_row(event))


def build_event_row(event: FailureEvent) -> dict[str, str]:
    """Build a CSV-safe row for a confirmed failure event."""

    return {
        "timestamp": event.timestamp,
        "source": event.source,
        "label": event.label,
        "confidence": f"{event.confidence:.4f}",
        "action": event.action,
        "screenshot_path": (
            event.screenshot_path.as_posix()
            if event.screenshot_path is not None
            else ""
        ),
    }


def alert_failure(
    source: str,
    label: str,
    confidence: float,
    beep_enabled: bool = ALERT_BEEP_ENABLED,
) -> None:
    """Print a terminal alert and optionally emit a safe terminal bell."""

    print(
        (
            "PRINTSENTINEL WARNING: confirmed failure "
            f"'{label}' on {source} at confidence {confidence:.2f}"
        ),
        file=sys.stderr,
    )

    if beep_enabled:
        print("\a", end="", flush=True)


def simulate_stop() -> str:
    """Simulate a printer stop action and return the action name."""

    return SimulatedPrinterController().stop_print().action


def simulate_pause() -> str:
    """Simulate a printer pause action and return the action name."""

    return SimulatedPrinterController().pause_print().action


def handle_confirmed_failure(
    frame: Any,
    source: str,
    label: str,
    confidence: float,
    timestamp: datetime | None = None,
    printer_action: str = PRINTER_ACTION,
    captures_dir: Path = CAPTURES_DIR,
    events_csv_path: Path = EVENTS_CSV_PATH,
) -> FailureEvent:
    """Run all configured responses for a confirmed failure."""

    ensure_action_paths()
    event_time = timestamp or now_local()
    action = normalize_printer_action(printer_action)
    screenshot_path: Path | None = None
    try:
        screenshot_path = save_failure_screenshot(
            frame,
            event_time,
            label,
            captures_dir=captures_dir,
        )
    except Exception as exc:  # noqa: BLE001 - printer response must still run.
        print(
            (
                "PRINTSENTINEL WARNING: failure screenshot could not be saved: "
                f"{exc.__class__.__name__}"
            ),
            file=sys.stderr,
        )

    event = FailureEvent(
        timestamp=event_time.isoformat(timespec="seconds"),
        source=source,
        label=label,
        confidence=confidence,
        action=action,
        screenshot_path=screenshot_path,
    )
    append_event_log(event, csv_path=events_csv_path)
    alert_failure(source, label, confidence)
    action_result = trigger_printer_response(action)
    try:
        dispatch_failure_notifications(event)
    except Exception as exc:  # noqa: BLE001 - notifications must not block printer action.
        print(
            (
                "PRINTSENTINEL WARNING: notification handling failed: "
                f"{exc.__class__.__name__}"
            ),
            file=sys.stderr,
        )

    return FailureEvent(
        timestamp=event.timestamp,
        source=event.source,
        label=event.label,
        confidence=event.confidence,
        action=event.action,
        screenshot_path=event.screenshot_path,
        action_success=action_result.success,
        action_message=action_result.message,
    )


def dispatch_failure_notifications(
    event: FailureEvent,
    dispatcher: NotificationDispatcher = _NOTIFICATION_DISPATCHER,
) -> None:
    """Dispatch notification alerts without blocking monitoring."""

    dispatcher.dispatch(lambda: send_failure_notifications(event))


def send_failure_notifications(event: FailureEvent) -> list[NotificationResult]:
    """Send notification alerts for a confirmed failure without raising."""

    notification = FailureNotification(
        timestamp=event.timestamp,
        source=event.source,
        label=event.label,
        confidence=event.confidence,
        action=event.action,
        screenshot_path=event.screenshot_path,
    )
    try:
        results = NotificationManager(build_enabled_providers()).send_failure_alert(
            notification
        )
    except Exception as exc:  # noqa: BLE001 - notifications must never crash monitoring.
        results = [
            NotificationResult(
                provider="notification_manager",
                destination_id="configured_providers",
                success=False,
                message=(
                    "Notification handling failed: "
                    f"{exc.__class__.__name__}"
                ),
            )
        ]

    safe_append_notification_results(notification, results)

    for result in results:
        if not result.success:
            print(
                (
                    "PRINTSENTINEL WARNING: notification failed "
                    f"({result.provider}/{result.destination_id}): {result.message}"
                ),
                file=sys.stderr,
            )

    return results


def get_simulated_action_name(action: str) -> str:
    """Return the supported simulated action name."""

    return normalize_printer_action(action)


def trigger_printer_response(
    action: str = PRINTER_ACTION,
    controller: PrinterController | None = None,
) -> PrinterCommandResult:
    """Run the selected printer response without crashing monitoring."""

    active_controller = controller or create_printer_controller()
    health_result = active_controller.healthcheck()
    if not health_result.success:
        print(f"PRINTSENTINEL WARNING: {health_result.message}", file=sys.stderr)

    action_result = execute_printer_action(active_controller, action)
    if not action_result.success:
        print(f"PRINTSENTINEL WARNING: {action_result.message}", file=sys.stderr)

    return action_result


def _run_simulated_action(action: str) -> str:
    """Run the configured simulated printer action."""

    return execute_printer_action(SimulatedPrinterController(), action).action
