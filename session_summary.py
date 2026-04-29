"""Session summary tracking for PrintSentinel runs."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import LOGS_DIR
from utils import now_local, safe_timestamp


@dataclass
class SessionSummary:
    """Track high-level metrics for one monitoring session."""

    source_name: str
    printer_backend: str
    printer_action: str
    started_at: datetime = field(default_factory=now_local)
    ended_at: datetime | None = None
    total_frames: int = 0
    detection_count: int = 0
    confirmed_failure_count: int = 0
    actions_triggered: int = 0
    screenshots_saved: int = 0
    last_action_result: str | None = None

    def record_frame(self) -> None:
        """Record that one frame was processed."""

        self.total_frames += 1

    def record_detection(self) -> None:
        """Record that a frame contained a failure-like detection."""

        self.detection_count += 1

    def record_confirmed_failure(self) -> None:
        """Record a newly confirmed failure sequence."""

        self.confirmed_failure_count += 1

    def record_action(self, screenshot_saved: bool, action_result: str) -> None:
        """Record a triggered response action."""

        self.actions_triggered += 1
        if screenshot_saved:
            self.screenshots_saved += 1
        self.last_action_result = action_result

    def finish(self) -> None:
        """Mark the session as ended."""

        self.ended_at = now_local()

    def to_dict(self) -> dict[str, str | int | None]:
        """Return a JSON-serializable summary."""

        ended_at = self.ended_at or now_local()
        duration_seconds = max(0.0, (ended_at - self.started_at).total_seconds())
        return {
            "source": self.source_name,
            "printer_backend": self.printer_backend,
            "printer_action": self.printer_action,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "ended_at": ended_at.isoformat(timespec="seconds"),
            "duration_seconds": round(duration_seconds, 2),
            "total_frames": self.total_frames,
            "detection_count": self.detection_count,
            "confirmed_failure_count": self.confirmed_failure_count,
            "actions_triggered": self.actions_triggered,
            "screenshots_saved": self.screenshots_saved,
            "last_action_result": self.last_action_result,
        }

    def write_json(self, logs_dir: Path = LOGS_DIR) -> Path:
        """Write the session summary JSON file and return its path."""

        logs_dir.mkdir(parents=True, exist_ok=True)
        filename = f"session_{safe_timestamp(self.started_at)}.json"
        summary_path = logs_dir / filename
        summary_path.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )
        return summary_path


def print_session_start(summary: SessionSummary) -> None:
    """Print a concise monitoring startup summary."""

    print("PrintSentinel session started")
    print(f"  Source: {summary.source_name}")
    print(f"  Printer backend: {summary.printer_backend}")
    print(f"  Printer action: {summary.printer_action}")


def print_session_summary(summary: SessionSummary, summary_path: Path | None) -> None:
    """Print a concise monitoring shutdown summary."""

    data = summary.to_dict()
    print("PrintSentinel session summary")
    print(f"  Source: {data['source']}")
    print(f"  Duration: {data['duration_seconds']}s")
    print(f"  Frames processed: {data['total_frames']}")
    print(f"  Detection frames: {data['detection_count']}")
    print(f"  Confirmed failures: {data['confirmed_failure_count']}")
    print(f"  Actions triggered: {data['actions_triggered']}")
    print(f"  Screenshots saved: {data['screenshots_saved']}")
    print(f"  Last action result: {data['last_action_result'] or 'none'}")
    if summary_path is not None:
        print(f"  Summary file: {summary_path}")
