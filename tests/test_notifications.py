"""Tests for notification management and providers."""

import builtins
import smtplib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import requests

from notifications.manager import NotificationManager, build_enabled_providers
from notifications.models import FailureNotification, NotificationResult
from notifications.providers.email import EmailProvider, parse_email_recipients
from notifications.providers.telegram import TelegramProvider
from notifications.providers.windows_toast import WindowsToastProvider


class RecordingProvider:
    """Notification provider that records sent alerts."""

    provider_name = "recording"
    destination_id = "test-destination"

    def __init__(self) -> None:
        """Create an empty recording provider."""

        self.notifications: list[FailureNotification] = []

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> NotificationResult:
        """Record a notification and return success."""

        self.notifications.append(notification)
        return NotificationResult(
            provider=self.provider_name,
            destination_id=self.destination_id,
            success=True,
            message="sent",
        )


class ExplodingProvider:
    """Notification provider that raises unexpectedly."""

    provider_name = "exploding"
    destination_id = "test-destination"

    def send_failure_alert(
        self,
        notification: FailureNotification,
    ) -> NotificationResult:
        """Raise an unexpected provider error."""

        raise RuntimeError("boom")


class FakeTelegramResponse:
    """Minimal requests response stand-in."""

    def __init__(self, error: requests.RequestException | None = None) -> None:
        """Create a fake response with an optional HTTP error."""

        self._error = error

    def raise_for_status(self) -> None:
        """Raise the configured HTTP error if present."""

        if self._error is not None:
            raise self._error


class FakeTelegramSession:
    """Requests-like session that records Telegram posts."""

    def __init__(
        self,
        error: Exception | None = None,
        response_error: requests.RequestException | None = None,
    ) -> None:
        """Create a fake Telegram session."""

        self.error = error
        self.response_error = response_error
        self.posts: list[dict[str, object]] = []

    def post(self, url, data, timeout, files=None):
        """Record a Telegram POST call."""

        self.posts.append(
            {
                "url": url,
                "data": data,
                "timeout": timeout,
                "files": files,
            }
        )
        if self.error is not None:
            raise self.error
        return FakeTelegramResponse(error=self.response_error)


def make_notification() -> FailureNotification:
    """Build a representative failure notification."""

    return FailureNotification(
        timestamp="2026-04-29T12:30:01+03:00",
        source="Sample video",
        label="spaghetti",
        confidence=0.91,
        action="stop",
        screenshot_path=Path("captures/failure.jpg"),
    )


def test_notification_manager_sends_to_provider() -> None:
    """Manager should send a failure alert through configured providers."""

    provider = RecordingProvider()
    notification = make_notification()

    results = NotificationManager([provider]).send_failure_alert(notification)

    assert provider.notifications == [notification]
    assert results == [
        NotificationResult(
            provider="recording",
            destination_id="test-destination",
            success=True,
            message="sent",
        )
    ]


def test_notification_manager_catches_provider_exception() -> None:
    """Manager should convert unexpected provider errors into failed results."""

    results = NotificationManager([ExplodingProvider()]).send_failure_alert(
        make_notification()
    )

    assert len(results) == 1
    assert results[0].provider == "exploding"
    assert not results[0].success
    assert "RuntimeError" in results[0].message


def test_notification_manager_returns_empty_list_without_providers() -> None:
    """Manager should no-op cleanly without providers."""

    assert NotificationManager().send_failure_alert(make_notification()) == []


def test_provider_factory_returns_no_providers_when_global_disabled() -> None:
    """Global notification disable should prevent provider construction."""

    assert (
        build_enabled_providers(
            notifications_enabled=False,
            windows_notifications_enabled=True,
        )
        == []
    )


def test_provider_factory_includes_windows_provider_when_enabled() -> None:
    """Factory should include Windows provider when both switches are enabled."""

    providers = build_enabled_providers(
        notifications_enabled=True,
        windows_notifications_enabled=True,
        windows_app_name="Test App",
    )

    assert len(providers) == 1
    assert isinstance(providers[0], WindowsToastProvider)
    assert providers[0].destination_id == "Test App"


def test_provider_factory_includes_only_enabled_providers() -> None:
    """Factory should honor global and provider-specific notification switches."""

    providers = build_enabled_providers(
        notifications_enabled=True,
        windows_notifications_enabled=False,
        telegram_notifications_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
        email_notifications_enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        smtp_username="user",
        smtp_password="password",
        email_from="from@example.com",
        email_to="one@example.com,two@example.com",
        notification_timeout_seconds=4.0,
    )

    assert [provider.provider_name for provider in providers] == ["telegram", "email"]


def test_windows_provider_skips_on_non_windows(monkeypatch) -> None:
    """Windows provider should safely skip on non-Windows platforms."""

    monkeypatch.setattr("platform.system", lambda: "Linux")

    result = WindowsToastProvider().send_failure_alert(make_notification())

    assert result.success
    assert result.message == "Skipped: not Windows"


def test_windows_provider_handles_missing_dependency(monkeypatch) -> None:
    """Missing windows-toasts dependency should return a failed result."""

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "windows_toasts":
            raise ImportError("missing windows_toasts")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "windows_toasts", raising=False)

    result = WindowsToastProvider().send_failure_alert(make_notification())

    assert not result.success
    assert "windows-toasts" in result.message


def test_windows_provider_sends_with_optional_dependency(monkeypatch) -> None:
    """Windows provider should use windows-toasts when available."""

    shown_toasts: list[object] = []

    class FakeToast:
        """Minimal windows_toasts Toast stand-in."""

        def __init__(self) -> None:
            """Create an empty fake toast."""

            self.text_fields: list[str] = []

    class FakeWindowsToaster:
        """Minimal windows_toasts WindowsToaster stand-in."""

        def __init__(self, app_name: str) -> None:
            """Create a fake toaster."""

            self.app_name = app_name

        def show_toast(self, toast: object) -> None:
            """Record a shown toast."""

            shown_toasts.append(SimpleNamespace(app_name=self.app_name, toast=toast))

    fake_module = ModuleType("windows_toasts")
    fake_module.Toast = FakeToast
    fake_module.WindowsToaster = FakeWindowsToaster

    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setitem(sys.modules, "windows_toasts", fake_module)

    result = WindowsToastProvider(app_name="PrintSentinel Test").send_failure_alert(
        make_notification()
    )

    assert result.success
    assert shown_toasts[0].app_name == "PrintSentinel Test"
    assert "spaghetti" in shown_toasts[0].toast.text_fields[1]


def test_telegram_missing_token_returns_failure() -> None:
    """Telegram provider should fail safely when bot token is missing."""

    result = TelegramProvider(
        bot_token="",
        chat_id="chat",
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "token" in result.message.lower()


def test_telegram_missing_chat_id_returns_failure() -> None:
    """Telegram provider should fail safely when chat ID is missing."""

    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="",
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "chat" in result.message.lower()
    assert "secret-token" not in result.message


def test_telegram_text_only_send_uses_send_message() -> None:
    """Telegram text-only alerts should call sendMessage."""

    session = FakeTelegramSession()
    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="123",
        send_screenshot=False,
        timeout_seconds=2.5,
        session=session,
    ).send_failure_alert(make_notification())

    assert result.success
    assert session.posts[0]["url"].endswith("/sendMessage")
    assert session.posts[0]["data"]["chat_id"] == "123"
    assert "spaghetti" in session.posts[0]["data"]["text"]
    assert session.posts[0]["timeout"] == 2.5
    assert session.posts[0]["files"] is None


def test_telegram_screenshot_send_uses_send_photo(tmp_path: Path) -> None:
    """Telegram screenshot alerts should call sendPhoto when enabled."""

    screenshot_path = tmp_path / "failure.jpg"
    screenshot_path.write_bytes(b"fake image")
    session = FakeTelegramSession()
    notification = make_notification()
    notification = FailureNotification(
        timestamp=notification.timestamp,
        source=notification.source,
        label=notification.label,
        confidence=notification.confidence,
        action=notification.action,
        screenshot_path=screenshot_path,
    )

    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="123",
        send_screenshot=True,
        session=session,
    ).send_failure_alert(notification)

    assert result.success
    assert session.posts[0]["url"].endswith("/sendPhoto")
    assert session.posts[0]["data"]["chat_id"] == "123"
    assert "spaghetti" in session.posts[0]["data"]["caption"]
    assert "photo" in session.posts[0]["files"]


def test_telegram_missing_screenshot_falls_back_to_text(tmp_path: Path) -> None:
    """Missing screenshots should fall back to Telegram sendMessage."""

    session = FakeTelegramSession()
    notification = make_notification()
    notification = FailureNotification(
        timestamp=notification.timestamp,
        source=notification.source,
        label=notification.label,
        confidence=notification.confidence,
        action=notification.action,
        screenshot_path=tmp_path / "missing.jpg",
    )

    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="123",
        send_screenshot=True,
        session=session,
    ).send_failure_alert(notification)

    assert result.success
    assert session.posts[0]["url"].endswith("/sendMessage")
    assert session.posts[0]["files"] is None


def test_telegram_oversized_screenshot_falls_back_to_text(tmp_path: Path) -> None:
    """Oversized screenshots should fall back to Telegram sendMessage."""

    screenshot_path = tmp_path / "large.jpg"
    screenshot_path.write_bytes(b"x" * 2048)
    session = FakeTelegramSession()
    notification = make_notification()
    notification = FailureNotification(
        timestamp=notification.timestamp,
        source=notification.source,
        label=notification.label,
        confidence=notification.confidence,
        action=notification.action,
        screenshot_path=screenshot_path,
    )

    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="123",
        send_screenshot=True,
        max_screenshot_mb=0.0001,
        session=session,
    ).send_failure_alert(notification)

    assert result.success
    assert session.posts[0]["url"].endswith("/sendMessage")
    assert session.posts[0]["files"] is None


def test_telegram_http_error_returns_failed_result() -> None:
    """Telegram HTTP errors should return failed results without leaking tokens."""

    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="123",
        session=FakeTelegramSession(
            response_error=requests.HTTPError("https://api.telegram.org/botsecret-token")
        ),
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "HTTPError" in result.message
    assert "secret-token" not in result.message


def test_telegram_request_exception_returns_failed_result() -> None:
    """Telegram timeouts and request exceptions should fail safely."""

    result = TelegramProvider(
        bot_token="secret-token",
        chat_id="123",
        session=FakeTelegramSession(error=requests.Timeout("secret-token")),
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "timed out" in result.message
    assert "secret-token" not in result.message


def test_email_missing_smtp_config_returns_failure() -> None:
    """Email provider should fail safely when SMTP config is incomplete."""

    result = EmailProvider(
        smtp_host="",
        smtp_port=0,
        smtp_security="ssl",
        username="",
        password="",
        sender="",
        recipients="",
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "SMTP host" in result.message
    assert "SMTP password" in result.message


def test_email_parses_multiple_recipients() -> None:
    """Email recipient parsing should ignore blank entries."""

    assert parse_email_recipients("one@example.com, , two@example.com") == [
        "one@example.com",
        "two@example.com",
    ]


def test_email_sends_text_only(monkeypatch) -> None:
    """Email provider should send a text-only SMTP SSL message."""

    sent_messages: list[object] = []

    class FakeSMTP:
        """SMTP SSL stand-in."""

        def __init__(self, host, port, timeout, context):
            """Record connection settings."""

            self.host = host
            self.port = port
            self.timeout = timeout
            self.context = context

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def login(self, username, password):
            self.username = username
            self.password = password

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    result = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        username="user",
        password="secret-password",
        sender="from@example.com",
        recipients="one@example.com, two@example.com",
        send_screenshot=False,
    ).send_failure_alert(make_notification())

    assert result.success
    assert sent_messages[0]["To"] == "one@example.com, two@example.com"
    assert sent_messages[0].get_content_maintype() == "text"


def test_email_attaches_screenshot_when_enabled(monkeypatch, tmp_path: Path) -> None:
    """Email provider should attach screenshots when configured."""

    sent_messages: list[object] = []

    class FakeSMTP:
        """SMTP STARTTLS stand-in."""

        def __init__(self, host, port, timeout):
            """Record connection settings."""

            self.host = host
            self.port = port
            self.timeout = timeout
            self.started_tls = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def starttls(self, context):
            self.started_tls = True

        def login(self, username, password):
            self.username = username
            self.password = password

        def send_message(self, message):
            sent_messages.append(message)

    screenshot_path = tmp_path / "failure.jpg"
    screenshot_path.write_bytes(b"fake image")
    notification = make_notification()
    notification = FailureNotification(
        timestamp=notification.timestamp,
        source=notification.source,
        label=notification.label,
        confidence=notification.confidence,
        action=notification.action,
        screenshot_path=screenshot_path,
    )

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)

    result = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_security="starttls",
        username="user",
        password="secret-password",
        sender="from@example.com",
        recipients=["one@example.com"],
        send_screenshot=True,
    ).send_failure_alert(notification)

    assert result.success
    assert sent_messages[0].is_multipart()
    assert any(part.get_filename() == "failure.jpg" for part in sent_messages[0].walk())


def test_email_missing_screenshot_falls_back_to_text(monkeypatch, tmp_path: Path) -> None:
    """Missing screenshots should not prevent text-only email alerts."""

    sent_messages: list[object] = []

    class FakeSMTP:
        """SMTP SSL stand-in."""

        def __init__(self, host, port, timeout, context):
            """Ignore connection settings."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def login(self, username, password):
            self.username = username

        def send_message(self, message):
            sent_messages.append(message)

    notification = make_notification()
    notification = FailureNotification(
        timestamp=notification.timestamp,
        source=notification.source,
        label=notification.label,
        confidence=notification.confidence,
        action=notification.action,
        screenshot_path=tmp_path / "missing.jpg",
    )

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    result = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        username="user",
        password="secret-password",
        sender="from@example.com",
        recipients="one@example.com",
        send_screenshot=True,
    ).send_failure_alert(notification)

    assert result.success
    assert sent_messages[0].get_content_maintype() == "text"


def test_email_oversized_screenshot_falls_back_to_text(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Oversized screenshots should not be attached to email alerts."""

    sent_messages: list[object] = []

    class FakeSMTP:
        """SMTP SSL stand-in."""

        def __init__(self, host, port, timeout, context):
            """Ignore connection settings."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def login(self, username, password):
            self.username = username

        def send_message(self, message):
            sent_messages.append(message)

    screenshot_path = tmp_path / "large.jpg"
    screenshot_path.write_bytes(b"x" * 2048)
    notification = make_notification()
    notification = FailureNotification(
        timestamp=notification.timestamp,
        source=notification.source,
        label=notification.label,
        confidence=notification.confidence,
        action=notification.action,
        screenshot_path=screenshot_path,
    )

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    result = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        username="user",
        password="secret-password",
        sender="from@example.com",
        recipients="one@example.com",
        send_screenshot=True,
        max_screenshot_mb=0.0001,
    ).send_failure_alert(notification)

    assert result.success
    assert sent_messages[0].get_content_maintype() == "text"


def test_email_handles_smtp_auth_failure(monkeypatch) -> None:
    """Email auth failures should return failed results without leaking passwords."""

    class FakeSMTP:
        """Failing SMTP SSL stand-in."""

        def __init__(self, host, port, timeout, context):
            """Ignore connection settings."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def login(self, username, password):
            raise smtplib.SMTPAuthenticationError(535, b"secret-password")

        def send_message(self, message):
            raise AssertionError("send_message should not run")

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    result = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        username="user",
        password="secret-password",
        sender="from@example.com",
        recipients="one@example.com",
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "authentication failed" in result.message
    assert "secret-password" not in result.message


def test_email_unexpected_error_does_not_leak_password(monkeypatch) -> None:
    """Unexpected SMTP errors should not leak configured passwords."""

    class FakeSMTP:
        """Failing SMTP SSL stand-in."""

        def __init__(self, host, port, timeout, context):
            """Ignore connection settings."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def login(self, username, password):
            raise RuntimeError("secret-password")

        def send_message(self, message):
            raise AssertionError("send_message should not run")

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)

    result = EmailProvider(
        smtp_host="smtp.example.com",
        smtp_port=465,
        smtp_security="ssl",
        username="user",
        password="secret-password",
        sender="from@example.com",
        recipients="one@example.com",
    ).send_failure_alert(make_notification())

    assert not result.success
    assert "RuntimeError" in result.message
    assert "secret-password" not in result.message
