"""Tests for notification management and providers."""

import builtins
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from notifications.manager import NotificationManager, build_enabled_providers
from notifications.models import FailureNotification, NotificationResult
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
    assert "boom" in results[0].message


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
