"""Notification helpers for confirmed PrintSentinel failures."""

from notifications.models import FailureNotification, NotificationResult

__all__ = [
    "FailureNotification",
    "NotificationManager",
    "NotificationResult",
    "build_enabled_providers",
]


def __getattr__(name: str) -> object:
    """Lazily expose manager helpers without creating config import cycles."""

    if name in {"NotificationManager", "build_enabled_providers"}:
        from notifications.manager import NotificationManager, build_enabled_providers

        return {
            "NotificationManager": NotificationManager,
            "build_enabled_providers": build_enabled_providers,
        }[name]

    raise AttributeError(f"module 'notifications' has no attribute {name!r}")
