"""Notification data models."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FailureNotification:
    """Information sent to notification providers after a confirmed failure."""

    timestamp: str
    source: str
    label: str
    confidence: float
    action: str
    screenshot_path: Path | None


@dataclass(frozen=True)
class NotificationResult:
    """Result returned by a notification provider."""

    provider: str
    destination_id: str
    success: bool
    message: str
