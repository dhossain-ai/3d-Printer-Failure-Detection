"""Tests for shared utility helpers."""

from datetime import datetime

from utils import AlertCooldown, safe_filename_part, safe_timestamp


def test_safe_timestamp_uses_filename_safe_format() -> None:
    """Timestamps should be stable and safe for filenames."""

    timestamp = datetime(2026, 4, 29, 12, 30, 1, 123456)

    assert safe_timestamp(timestamp) == "20260429_123001_123456"


def test_safe_filename_part_removes_unsafe_characters() -> None:
    """Labels should become conservative filename fragments."""

    assert safe_filename_part(" Spaghetti / Stringing! ") == "spaghetti_stringing"
    assert safe_filename_part("   ") == "unknown"


def test_alert_cooldown_ready_and_remaining_seconds() -> None:
    """Cooldown should block repeated triggers until enough time passes."""

    cooldown = AlertCooldown(seconds=10)

    assert cooldown.is_ready(100.0)
    cooldown.mark_triggered(100.0)

    assert not cooldown.is_ready(105.0)
    assert cooldown.remaining_seconds(105.0) == 5
    assert cooldown.is_ready(110.0)
    assert cooldown.remaining_seconds(111.0) == 0
