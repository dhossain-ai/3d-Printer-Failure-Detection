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
    SIMULATED_ACTION,
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


@dataclass(frozen=True)
class FailureEvent:
    """Recorded response for a confirmed print failure."""

    timestamp: str
    source: str
    label: str
    confidence: float
    action: str
    screenshot_path: Path


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
        "screenshot_path": str(event.screenshot_path),
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

    print("SIMULATED PRINTER ACTION: STOP requested.", file=sys.stderr)
    return "stop"


def simulate_pause() -> str:
    """Simulate a printer pause action and return the action name."""

    print("SIMULATED PRINTER ACTION: PAUSE requested.", file=sys.stderr)
    return "pause"


def handle_confirmed_failure(
    frame: Any,
    source: str,
    label: str,
    confidence: float,
    timestamp: datetime | None = None,
    simulated_action: str = SIMULATED_ACTION,
) -> FailureEvent:
    """Run all Phase 2 responses for a confirmed failure."""

    ensure_action_paths()
    event_time = timestamp or now_local()
    action = get_simulated_action_name(simulated_action)
    screenshot_path = save_failure_screenshot(frame, event_time, label)

    event = FailureEvent(
        timestamp=event_time.isoformat(timespec="seconds"),
        source=source,
        label=label,
        confidence=confidence,
        action=action,
        screenshot_path=screenshot_path,
    )
    append_event_log(event)
    alert_failure(source, label, confidence)
    _run_simulated_action(action)

    return event


def get_simulated_action_name(action: str) -> str:
    """Return the supported simulated action name."""

    normalized_action = action.lower().strip()
    if normalized_action == "pause":
        return "pause"

    return "stop"


def _run_simulated_action(action: str) -> str:
    """Run the configured simulated printer action."""

    if get_simulated_action_name(action) == "pause":
        return simulate_pause()

    return simulate_stop()
