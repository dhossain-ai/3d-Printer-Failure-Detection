"""Windows desktop toast notification provider."""

import platform

from notifications.models import FailureNotification, NotificationResult


class WindowsToastProvider:
    """Send confirmed-failure alerts as Windows desktop toast notifications."""

    provider_name = "windows_toast"

    def __init__(self, app_name: str = "PrintSentinel") -> None:
        """Create a Windows toast notification provider."""

        self._app_name = app_name.strip() or "PrintSentinel"
        self.destination_id = self._app_name

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> NotificationResult:
        """Send a Windows toast alert if the platform and dependency support it."""

        if platform.system() != "Windows":
            return NotificationResult(
                provider=self.provider_name,
                destination_id=self.destination_id,
                success=True,
                message="Skipped: not Windows",
            )

        try:
            from windows_toasts import Toast, WindowsToaster
        except ImportError:
            return NotificationResult(
                provider=self.provider_name,
                destination_id=self.destination_id,
                success=False,
                message=(
                    "Missing optional dependency: install windows-toasts to enable "
                    "Windows desktop notifications."
                ),
            )

        try:
            toaster = WindowsToaster(self._app_name)
            toast = Toast()
            toast.text_fields = [
                "PrintSentinel confirmed failure",
                _format_notification_body(notification),
            ]
            toaster.show_toast(toast)
        except Exception as exc:  # noqa: BLE001 - notifications must never crash monitoring.
            return NotificationResult(
                provider=self.provider_name,
                destination_id=self.destination_id,
                success=False,
                message=f"Windows toast notification failed: {exc}",
            )

        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=True,
            message="Windows toast notification sent.",
        )


def _format_notification_body(notification: FailureNotification) -> str:
    """Build concise text for the desktop notification body."""

    screenshot = (
        str(notification.screenshot_path)
        if notification.screenshot_path is not None
        else "not saved"
    )
    return (
        f"Label: {notification.label} | "
        f"Confidence: {notification.confidence:.2f} | "
        f"Source: {notification.source} | "
        f"Action: {notification.action} | "
        f"Screenshot: {screenshot}"
    )
