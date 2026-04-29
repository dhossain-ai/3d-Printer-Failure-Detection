"""Small shared helpers for PrintSentinel."""

import re
from dataclasses import dataclass
from datetime import datetime


def now_local() -> datetime:
    """Return the current local timezone-aware datetime."""

    return datetime.now().astimezone()


def safe_timestamp(timestamp: datetime) -> str:
    """Format a timestamp for use in filenames."""

    return timestamp.strftime("%Y%m%d_%H%M%S_%f")


def safe_filename_part(value: str) -> str:
    """Return a conservative filename fragment."""

    safe_value = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip().lower())
    return safe_value.strip("_") or "unknown"


@dataclass
class AlertCooldown:
    """Track whether a confirmed failure action is inside its cooldown window."""

    seconds: int
    last_triggered_at: float | None = None

    def is_ready(self, now_seconds: float) -> bool:
        """Return whether an alert action may run now."""

        if self.last_triggered_at is None:
            return True

        return now_seconds - self.last_triggered_at >= self.seconds

    def mark_triggered(self, now_seconds: float) -> None:
        """Record that an alert action just ran."""

        self.last_triggered_at = now_seconds

    def remaining_seconds(self, now_seconds: float) -> int:
        """Return whole seconds remaining in the cooldown window."""

        if self.last_triggered_at is None:
            return 0

        elapsed = now_seconds - self.last_triggered_at
        remaining = self.seconds - elapsed
        return max(0, int(round(remaining)))
