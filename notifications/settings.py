"""Local notification settings persistence and validation."""

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from notifications.models import FailureNotification, NotificationResult

BASE_DIR = Path(__file__).resolve().parents[1]
LOCAL_NOTIFICATION_SETTINGS_PATH = (
    BASE_DIR / "config" / "local_notification_settings.json"
)

DEFAULT_LOCAL_NOTIFICATION_SETTINGS: dict[str, Any] = {
    "NOTIFICATIONS_ENABLED": False,
    "WINDOWS_NOTIFICATIONS_ENABLED": False,
    "WINDOWS_NOTIFICATION_APP_NAME": "PrintSentinel",
    "TELEGRAM_NOTIFICATIONS_ENABLED": False,
    "TELEGRAM_BOT_TOKEN": "",
    "TELEGRAM_CHAT_ID": "",
    "TELEGRAM_SEND_SCREENSHOT": True,
    "EMAIL_NOTIFICATIONS_ENABLED": False,
    "SMTP_HOST": "",
    "SMTP_PORT": 465,
    "SMTP_SECURITY": "ssl",
    "SMTP_USERNAME": "",
    "SMTP_PASSWORD": "",
    "EMAIL_FROM": "",
    "EMAIL_TO": "",
    "EMAIL_SEND_SCREENSHOT": True,
    "NOTIFICATION_TIMEOUT_SECONDS": 5.0,
    "NOTIFICATION_MAX_SCREENSHOT_MB": 5.0,
}

_BOOL_KEYS = {
    "NOTIFICATIONS_ENABLED",
    "WINDOWS_NOTIFICATIONS_ENABLED",
    "TELEGRAM_NOTIFICATIONS_ENABLED",
    "TELEGRAM_SEND_SCREENSHOT",
    "EMAIL_NOTIFICATIONS_ENABLED",
    "EMAIL_SEND_SCREENSHOT",
}


def load_notification_settings(
    path: Path = LOCAL_NOTIFICATION_SETTINGS_PATH,
) -> dict[str, Any]:
    """Load local notification settings or return defaults when missing."""

    if not path.exists():
        return DEFAULT_LOCAL_NOTIFICATION_SETTINGS.copy()

    try:
        with path.open("r", encoding="utf-8") as settings_file:
            raw_settings = json.load(settings_file)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_LOCAL_NOTIFICATION_SETTINGS.copy()

    if not isinstance(raw_settings, dict):
        return DEFAULT_LOCAL_NOTIFICATION_SETTINGS.copy()

    return normalize_notification_settings(raw_settings)


def save_notification_settings(
    settings: Mapping[str, Any],
    path: Path = LOCAL_NOTIFICATION_SETTINGS_PATH,
) -> dict[str, Any]:
    """Validate and save local notification settings."""

    normalized = normalize_notification_settings(settings)
    errors = validate_notification_settings(normalized)
    if errors:
        raise ValueError("\n".join(errors))

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as settings_file:
        json.dump(normalized, settings_file, indent=2, sort_keys=True)
        settings_file.write("\n")

    return normalized


def normalize_notification_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Return settings with known keys and simple scalar values."""

    normalized = DEFAULT_LOCAL_NOTIFICATION_SETTINGS.copy()
    for key in normalized:
        if key in settings:
            normalized[key] = settings[key]

    for key in _BOOL_KEYS:
        normalized[key] = _coerce_bool(normalized[key])

    normalized["SMTP_PORT"] = _coerce_int_or_original(normalized["SMTP_PORT"])
    normalized["NOTIFICATION_TIMEOUT_SECONDS"] = _coerce_float_or_original(
        normalized["NOTIFICATION_TIMEOUT_SECONDS"]
    )
    normalized["NOTIFICATION_MAX_SCREENSHOT_MB"] = _coerce_float_or_original(
        normalized["NOTIFICATION_MAX_SCREENSHOT_MB"]
    )

    for key, value in normalized.items():
        if key not in _BOOL_KEYS and key not in {
            "SMTP_PORT",
            "NOTIFICATION_TIMEOUT_SECONDS",
            "NOTIFICATION_MAX_SCREENSHOT_MB",
        }:
            normalized[key] = str(value).strip()

    normalized["SMTP_SECURITY"] = str(normalized["SMTP_SECURITY"]).lower().strip()
    return normalized


def validate_notification_settings(settings: Mapping[str, Any]) -> list[str]:
    """Return user-friendly validation errors for enabled providers."""

    normalized = normalize_notification_settings(settings)
    errors: list[str] = []

    if normalized["TELEGRAM_NOTIFICATIONS_ENABLED"]:
        if not normalized["TELEGRAM_BOT_TOKEN"]:
            errors.append("Telegram bot token is required when Telegram is enabled.")
        if not normalized["TELEGRAM_CHAT_ID"]:
            errors.append("Telegram chat ID is required when Telegram is enabled.")

    if normalized["EMAIL_NOTIFICATIONS_ENABLED"]:
        if not normalized["SMTP_HOST"]:
            errors.append("SMTP host is required when email is enabled.")
        if not isinstance(normalized["SMTP_PORT"], int) or normalized["SMTP_PORT"] <= 0:
            errors.append("SMTP port must be a positive number.")
        if normalized["SMTP_SECURITY"] not in {"ssl", "starttls", "none"}:
            errors.append("SMTP security must be ssl, starttls, or none.")
        if not normalized["SMTP_USERNAME"]:
            errors.append("SMTP username is required when email is enabled.")
        if not normalized["SMTP_PASSWORD"]:
            errors.append("SMTP password is required when email is enabled.")
        if not normalized["EMAIL_FROM"]:
            errors.append("From email is required when email is enabled.")
        if not parse_recipient_emails(normalized["EMAIL_TO"]):
            errors.append("At least one recipient email is required when email is enabled.")

    max_screenshot_mb = normalized["NOTIFICATION_MAX_SCREENSHOT_MB"]
    if not isinstance(max_screenshot_mb, (float, int)) or max_screenshot_mb <= 0:
        errors.append("Notification max screenshot MB must be a positive number.")

    return errors


def parse_recipient_emails(value: str) -> list[str]:
    """Parse comma-separated email recipients."""

    return [recipient.strip() for recipient in value.split(",") if recipient.strip()]


def build_provider_factory_kwargs(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Build keyword arguments for the notification provider factory."""

    normalized = normalize_notification_settings(settings)
    return {
        "notifications_enabled": normalized["NOTIFICATIONS_ENABLED"],
        "windows_notifications_enabled": normalized["WINDOWS_NOTIFICATIONS_ENABLED"],
        "windows_app_name": normalized["WINDOWS_NOTIFICATION_APP_NAME"],
        "telegram_notifications_enabled": normalized[
            "TELEGRAM_NOTIFICATIONS_ENABLED"
        ],
        "telegram_bot_token": normalized["TELEGRAM_BOT_TOKEN"],
        "telegram_chat_id": normalized["TELEGRAM_CHAT_ID"],
        "telegram_send_screenshot": normalized["TELEGRAM_SEND_SCREENSHOT"],
        "email_notifications_enabled": normalized["EMAIL_NOTIFICATIONS_ENABLED"],
        "smtp_host": normalized["SMTP_HOST"],
        "smtp_port": _safe_int(normalized["SMTP_PORT"], 465),
        "smtp_security": normalized["SMTP_SECURITY"],
        "smtp_username": normalized["SMTP_USERNAME"],
        "smtp_password": normalized["SMTP_PASSWORD"],
        "email_from": normalized["EMAIL_FROM"],
        "email_to": normalized["EMAIL_TO"],
        "email_send_screenshot": normalized["EMAIL_SEND_SCREENSHOT"],
        "notification_timeout_seconds": _safe_float(
            normalized["NOTIFICATION_TIMEOUT_SECONDS"],
            5.0,
        ),
        "notification_max_screenshot_mb": _safe_float(
            normalized["NOTIFICATION_MAX_SCREENSHOT_MB"],
            5.0,
        ),
    }


def send_test_notification(
    settings: Mapping[str, Any],
    provider_builder: Callable[..., list[Any]] | None = None,
    manager_factory: Callable[[list[Any]], Any] | None = None,
) -> list[NotificationResult]:
    """Send a test notification through enabled providers."""

    errors = validate_notification_settings(settings)
    if errors:
        return [
            NotificationResult(
                provider="settings",
                destination_id="local_notification_settings",
                success=False,
                message="\n".join(errors),
            )
        ]

    if provider_builder is None or manager_factory is None:
        from notifications.manager import NotificationManager, build_enabled_providers

        provider_builder = provider_builder or build_enabled_providers
        manager_factory = manager_factory or NotificationManager

    providers = provider_builder(**build_provider_factory_kwargs(settings))
    notification = FailureNotification(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        source="Notification settings",
        label="test",
        confidence=1.0,
        action="test",
        screenshot_path=None,
    )
    return manager_factory(providers).send_failure_alert(notification)


def _coerce_bool(value: Any) -> bool:
    """Coerce common UI/env boolean values."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_int_or_original(value: Any) -> int | Any:
    """Coerce a value to int, preserving invalid values for validation."""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return value


def _coerce_float_or_original(value: Any) -> float | Any:
    """Coerce a value to float, preserving invalid values for validation."""

    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return value


def _safe_int(value: Any, default: int) -> int:
    """Return an int or fallback default."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    """Return a float or fallback default."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default
