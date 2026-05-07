"""Notification provider orchestration."""

from collections.abc import Iterable

from config import (
    EMAIL_FROM,
    EMAIL_NOTIFICATIONS_ENABLED,
    EMAIL_SEND_SCREENSHOT,
    EMAIL_TO,
    NOTIFICATIONS_ENABLED,
    NOTIFICATION_TIMEOUT_SECONDS,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SECURITY,
    SMTP_USERNAME,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_NOTIFICATIONS_ENABLED,
    TELEGRAM_SEND_SCREENSHOT,
    WINDOWS_NOTIFICATION_APP_NAME,
    WINDOWS_NOTIFICATIONS_ENABLED,
)
from notifications.models import FailureNotification, NotificationResult
from notifications.providers.base import NotificationProvider
from notifications.providers.email import EmailProvider
from notifications.providers.telegram import TelegramProvider
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
                        message=(
                            "Provider raised an unexpected error: "
                            f"{exc.__class__.__name__}"
                        ),
                    )
                )

        return results


def build_enabled_providers(
    notifications_enabled: bool = NOTIFICATIONS_ENABLED,
    windows_notifications_enabled: bool = WINDOWS_NOTIFICATIONS_ENABLED,
    windows_app_name: str = WINDOWS_NOTIFICATION_APP_NAME,
    telegram_notifications_enabled: bool = TELEGRAM_NOTIFICATIONS_ENABLED,
    telegram_bot_token: str = TELEGRAM_BOT_TOKEN,
    telegram_chat_id: str = TELEGRAM_CHAT_ID,
    telegram_send_screenshot: bool = TELEGRAM_SEND_SCREENSHOT,
    email_notifications_enabled: bool = EMAIL_NOTIFICATIONS_ENABLED,
    smtp_host: str = SMTP_HOST,
    smtp_port: int = SMTP_PORT,
    smtp_security: str = SMTP_SECURITY,
    smtp_username: str = SMTP_USERNAME,
    smtp_password: str = SMTP_PASSWORD,
    email_from: str = EMAIL_FROM,
    email_to: str = EMAIL_TO,
    email_send_screenshot: bool = EMAIL_SEND_SCREENSHOT,
    notification_timeout_seconds: float = NOTIFICATION_TIMEOUT_SECONDS,
) -> list[NotificationProvider]:
    """Build notification providers enabled by configuration."""

    if not notifications_enabled:
        return []

    providers: list[NotificationProvider] = []
    if windows_notifications_enabled:
        providers.append(WindowsToastProvider(app_name=windows_app_name))
    if telegram_notifications_enabled:
        providers.append(
            TelegramProvider(
                bot_token=telegram_bot_token,
                chat_id=telegram_chat_id,
                send_screenshot=telegram_send_screenshot,
                timeout_seconds=notification_timeout_seconds,
            )
        )
    if email_notifications_enabled:
        providers.append(
            EmailProvider(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_security=smtp_security,
                username=smtp_username,
                password=smtp_password,
                sender=email_from,
                recipients=email_to,
                send_screenshot=email_send_screenshot,
                timeout_seconds=notification_timeout_seconds,
            )
        )

    return providers
