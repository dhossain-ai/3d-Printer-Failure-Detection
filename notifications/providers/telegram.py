"""Telegram notification provider."""

from pathlib import Path
from typing import Any

import requests

from notifications.models import FailureNotification, NotificationResult
from notifications.screenshots import screenshot_unavailable_reason, screenshot_within_limit

TELEGRAM_API_BASE_URL = "https://api.telegram.org"


class TelegramProvider:
    """Send confirmed-failure alerts through Telegram Bot API."""

    provider_name = "telegram"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        send_screenshot: bool = True,
        timeout_seconds: float = 5.0,
        max_screenshot_mb: float = 5.0,
        session: Any | None = None,
    ) -> None:
        """Create a Telegram notification provider."""

        self._bot_token = bot_token.strip()
        self._chat_id = chat_id.strip()
        self._send_screenshot = send_screenshot
        self._timeout_seconds = timeout_seconds
        self._max_screenshot_mb = max_screenshot_mb
        self._session = session or requests
        self.destination_id = self._chat_id or "telegram"

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> NotificationResult:
        """Send a Telegram message or photo alert."""

        config_error = self._validate_config()
        if config_error is not None:
            return config_error

        try:
            if self._should_send_photo(notification.screenshot_path):
                return self._send_photo(notification)

            return self._send_message(
                notification,
                fallback_reason=self._screenshot_fallback_reason(
                    notification.screenshot_path
                ),
            )
        except requests.Timeout as exc:
            return self._failure_result(
                f"Telegram request timed out: {exc.__class__.__name__}"
            )
        except requests.RequestException as exc:
            return self._failure_result(
                f"Telegram request failed: {exc.__class__.__name__}"
            )
        except OSError as exc:
            return self._failure_result(f"Telegram screenshot could not be read: {exc}")
        except Exception as exc:  # noqa: BLE001 - providers must isolate failures.
            return self._failure_result(
                f"Telegram notification failed: {exc.__class__.__name__}"
            )

    def _validate_config(self) -> NotificationResult | None:
        """Return a failed result when required Telegram config is missing."""

        if not self._bot_token:
            return self._failure_result("Telegram bot token is not configured.")
        if not self._chat_id:
            return self._failure_result("Telegram chat ID is not configured.")
        if self._timeout_seconds <= 0:
            return self._failure_result("Telegram timeout must be greater than zero.")

        return None

    def _send_message(
        self,
        notification: FailureNotification,
        fallback_reason: str | None = None,
    ) -> NotificationResult:
        """Send a text-only Telegram alert."""

        response = self._session.post(
            self._api_url("sendMessage"),
            data={
                "chat_id": self._chat_id,
                "text": _format_message(notification),
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()

        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=True,
            message=(
                "Telegram message sent without screenshot "
                f"({fallback_reason})."
                if fallback_reason
                else "Telegram message sent."
            ),
        )

    def _send_photo(self, notification: FailureNotification) -> NotificationResult:
        """Send a Telegram alert with screenshot attachment."""

        screenshot_path = _require_screenshot_path(notification.screenshot_path)
        with screenshot_path.open("rb") as image_file:
            response = self._session.post(
                self._api_url("sendPhoto"),
                data={
                    "chat_id": self._chat_id,
                    "caption": _format_message(notification),
                },
                files={"photo": image_file},
                timeout=self._timeout_seconds,
            )
        response.raise_for_status()

        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=True,
            message="Telegram photo sent.",
        )

    def _should_send_photo(self, screenshot_path: Path | None) -> bool:
        """Return whether a screenshot should be sent as a Telegram photo."""

        return (
            self._send_screenshot
            and screenshot_within_limit(screenshot_path, self._max_screenshot_mb)
        )

    def _screenshot_fallback_reason(self, screenshot_path: Path | None) -> str | None:
        """Return a text-only fallback reason when screenshot sending was requested."""

        if not self._send_screenshot:
            return None
        return screenshot_unavailable_reason(screenshot_path, self._max_screenshot_mb)

    def _api_url(self, method: str) -> str:
        """Build a Telegram Bot API method URL."""

        return f"{TELEGRAM_API_BASE_URL}/bot{self._bot_token}/{method}"

    def _failure_result(self, message: str) -> NotificationResult:
        """Build a failed Telegram notification result."""

        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=False,
            message=message,
        )


def _format_message(notification: FailureNotification) -> str:
    """Build Telegram alert text."""

    screenshot = (
        str(notification.screenshot_path)
        if notification.screenshot_path is not None
        else "not saved"
    )
    return (
        "PrintSentinel confirmed failure\n"
        f"Time: {notification.timestamp}\n"
        f"Source: {notification.source}\n"
        f"Label: {notification.label}\n"
        f"Confidence: {notification.confidence:.2f}\n"
        f"Printer action: {notification.action}\n"
        f"Screenshot: {screenshot}"
    )


def _require_screenshot_path(screenshot_path: Path | None) -> Path:
    """Return a screenshot path after a type-narrowing check."""

    if screenshot_path is None:
        raise FileNotFoundError("screenshot path is not available")
    return screenshot_path
