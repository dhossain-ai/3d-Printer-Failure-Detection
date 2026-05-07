"""Notification provider orchestration."""

from collections.abc import Iterable

from config import (
    NOTIFICATIONS_ENABLED,
    WINDOWS_NOTIFICATION_APP_NAME,
    WINDOWS_NOTIFICATIONS_ENABLED,
)
from notifications.models import FailureNotification, NotificationResult
from notifications.providers.base import NotificationProvider
from notifications.providers.windows_toast import WindowsToastProvider


class NotificationManager:
    """Send confirmed-failure alerts through configured providers."""

    def __init__(self, providers: Iterable[NotificationProvider] | None = None) -> None:
        """Create a notification manager from provider instances."""

        self._providers = list(providers or [])

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> list[NotificationResult]:
        """Send a failure alert to each provider and collect results."""

        results: list[NotificationResult] = []
        for provider in self._providers:
            try:
                results.append(provider.send_failure_alert(notification))
            except Exception as exc:  # noqa: BLE001 - provider failures must be isolated.
                results.append(
                    NotificationResult(
                        provider=provider.provider_name,
                        destination_id=provider.destination_id,
                        success=False,
                        message=f"Provider raised an unexpected error: {exc}",
                    )
                )

        return results


def build_enabled_providers(
    notifications_enabled: bool = NOTIFICATIONS_ENABLED,
    windows_notifications_enabled: bool = WINDOWS_NOTIFICATIONS_ENABLED,
    windows_app_name: str = WINDOWS_NOTIFICATION_APP_NAME,
) -> list[NotificationProvider]:
    """Build notification providers enabled by configuration."""

    if not notifications_enabled:
        return []

    providers: list[NotificationProvider] = []
    if windows_notifications_enabled:
        providers.append(WindowsToastProvider(app_name=windows_app_name))

    return providers
