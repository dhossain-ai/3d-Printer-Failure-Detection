"""Notification provider interface."""

from typing import Protocol

from notifications.models import FailureNotification, NotificationResult


class NotificationProvider(Protocol):
    """Interface implemented by notification providers."""

    provider_name: str
    destination_id: str

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> NotificationResult:
        """Send a confirmed-failure alert."""
