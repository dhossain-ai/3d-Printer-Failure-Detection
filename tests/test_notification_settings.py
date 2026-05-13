"""Tests for local notification settings."""

from pathlib import Path

from notifications.models import FailureNotification, NotificationResult
from notifications.settings import (
    DEFAULT_LOCAL_NOTIFICATION_SETTINGS,
    load_notification_settings,
    mask_notification_settings,
    mask_secret,
    merge_notification_settings_update,
    parse_recipient_emails,
    sanitize_notification_results,
    save_notification_settings,
    send_test_notification,
    validate_notification_settings,
)


def test_load_notification_settings_returns_defaults_when_missing(
    tmp_path: Path,
) -> None:
    """Missing local settings files should load safe defaults."""

    settings = load_notification_settings(tmp_path / "missing.json")

    assert settings == DEFAULT_LOCAL_NOTIFICATION_SETTINGS


def test_save_and_load_notification_settings_json(tmp_path: Path) -> None:
    """Local notification settings should round-trip through JSON."""

    path = tmp_path / "config" / "local_notification_settings.json"
    settings = {
        "NOTIFICATIONS_ENABLED": True,
        "WINDOWS_NOTIFICATIONS_ENABLED": True,
        "TELEGRAM_NOTIFICATIONS_ENABLED": False,
        "EMAIL_NOTIFICATIONS_ENABLED": False,
        "SMTP_PORT": "587",
        "SMTP_SECURITY": "starttls",
    }

    saved = save_notification_settings(settings, path=path)
    loaded = load_notification_settings(path)

    assert path.exists()
    assert saved["NOTIFICATIONS_ENABLED"] is True
    assert loaded["WINDOWS_NOTIFICATIONS_ENABLED"] is True
    assert loaded["SMTP_PORT"] == 587
    assert loaded["SMTP_SECURITY"] == "starttls"


def test_save_rejects_invalid_enabled_provider_config(tmp_path: Path) -> None:
    """Invalid enabled provider settings should not be saved."""

    path = tmp_path / "config" / "local_notification_settings.json"
    settings = {
        "NOTIFICATIONS_ENABLED": True,
        "TELEGRAM_NOTIFICATIONS_ENABLED": True,
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
    }

    try:
        save_notification_settings(settings, path=path)
    except ValueError as exc:
        assert "Telegram bot token" in str(exc)
        assert "Telegram chat ID" in str(exc)
    else:
        raise AssertionError("Expected invalid settings to raise ValueError")

    assert not path.exists()


def test_disabled_provider_config_can_be_incomplete(tmp_path: Path) -> None:
    """Disabled providers should not require secrets or connection settings."""

    path = tmp_path / "config" / "local_notification_settings.json"

    saved = save_notification_settings(
        {
            "NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_NOTIFICATIONS_ENABLED": False,
            "EMAIL_NOTIFICATIONS_ENABLED": False,
        },
        path=path,
    )

    assert saved["TELEGRAM_BOT_TOKEN"] == ""
    assert path.exists()


def test_parse_recipient_emails_ignores_empty_entries() -> None:
    """Recipient parsing should support comma-separated local settings."""

    assert parse_recipient_emails("one@example.com, ,two@example.com,") == [
        "one@example.com",
        "two@example.com",
    ]


def test_validate_notification_settings_reports_errors() -> None:
    """Validation should return user-friendly messages."""

    errors = validate_notification_settings(
        {
            "EMAIL_NOTIFICATIONS_ENABLED": True,
            "SMTP_HOST": "",
            "SMTP_PORT": "not-a-number",
            "SMTP_USERNAME": "",
            "SMTP_PASSWORD": "",
            "EMAIL_FROM": "",
            "EMAIL_TO": "",
        }
    )

    assert "SMTP host is required when email is enabled." in errors
    assert "SMTP port must be a positive number." in errors
    assert "At least one recipient email is required when email is enabled." in errors


def test_send_test_notification_uses_provider_factory_and_manager() -> None:
    """Test notifications should use the provider factory and manager."""

    captured_kwargs: dict[str, object] = {}
    captured_notifications: list[FailureNotification] = []

    def fake_provider_builder(**kwargs):
        captured_kwargs.update(kwargs)
        return ["fake-provider"]

    class FakeManager:
        """NotificationManager stand-in."""

        def __init__(self, providers) -> None:
            """Record configured providers."""

            self.providers = providers

        def send_failure_alert(
            self,
            notification: FailureNotification,
        ) -> list[NotificationResult]:
            """Record the test notification and return success."""

            captured_notifications.append(notification)
            return [
                NotificationResult(
                    provider="fake",
                    destination_id="test",
                    success=True,
                    message="ok",
                )
            ]

    results = send_test_notification(
        {
            "NOTIFICATIONS_ENABLED": True,
            "WINDOWS_NOTIFICATIONS_ENABLED": True,
        },
        provider_builder=fake_provider_builder,
        manager_factory=FakeManager,
    )

    assert captured_kwargs["notifications_enabled"] is True
    assert captured_kwargs["windows_notifications_enabled"] is True
    assert captured_notifications[0].source == "Notification settings"
    assert captured_notifications[0].label == "test"
    assert results[0].success


def test_merge_notification_settings_update_keeps_existing_blank_secret() -> None:
    """Blank secret updates should preserve the current stored secret."""

    merged = merge_notification_settings_update(
        current_settings={
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "SMTP_PASSWORD": "secret-password",
        },
        incoming_settings={
            "TELEGRAM_BOT_TOKEN": "",
            "SMTP_PASSWORD": "",
        },
    )

    assert merged["TELEGRAM_BOT_TOKEN"] == "secret-token"
    assert merged["SMTP_PASSWORD"] == "secret-password"


def test_mask_notification_settings_hides_secrets() -> None:
    """Masked settings payloads should not expose raw secrets."""

    masked = mask_notification_settings(
        {
            "NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_BOT_TOKEN": "123456:ABCDEF",
            "TELEGRAM_CHAT_ID": "chat-1234",
            "SMTP_USERNAME": "printer@example.com",
            "SMTP_PASSWORD": "super-secret",
        }
    )

    assert masked["telegram_bot_token_masked"] == mask_secret("123456:ABCDEF")
    assert masked["smtp_password_masked"] == mask_secret("super-secret")
    assert "123456:ABCDEF" not in masked.values()
    assert "super-secret" not in masked.values()


def test_sanitize_notification_results_redacts_secret_text() -> None:
    """API result messages should redact configured secrets."""

    results = sanitize_notification_results(
        [
            NotificationResult(
                provider="telegram",
                destination_id="secret-chat",
                success=False,
                message="failed with secret-token and secret-password",
            )
        ],
        {
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "TELEGRAM_CHAT_ID": "secret-chat",
            "SMTP_PASSWORD": "secret-password",
        },
    )

    assert "[redacted]" in results[0]["message"]
    assert "secret-token" not in results[0]["message"]
    assert "secret-password" not in results[0]["message"]
    assert "secret-chat" not in results[0]["destination_id"]
