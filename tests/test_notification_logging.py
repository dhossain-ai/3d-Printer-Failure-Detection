"""Tests for notification result CSV logging."""

import csv
from pathlib import Path

from notifications.logging import (
    append_notification_results,
    safe_append_notification_results,
)
from notifications.models import FailureNotification, NotificationResult


def make_notification() -> FailureNotification:
    """Build a representative notification event."""

    return FailureNotification(
        timestamp="2026-04-29T12:30:01+03:00",
        source="Sample video",
        label="spaghetti",
        confidence=0.9,
        action="stop",
        screenshot_path=Path("captures/failure.jpg"),
    )


def make_result(provider: str = "telegram") -> NotificationResult:
    """Build a representative notification result."""

    return NotificationResult(
        provider=provider,
        destination_id="destination",
        success=True,
        message="sent",
    )


def test_notification_log_writes_header_and_row(tmp_path: Path) -> None:
    """Notification logging should create a CSV header and result row."""

    csv_path = tmp_path / "logs" / "notifications.csv"

    append_notification_results(make_notification(), [make_result()], csv_path=csv_path)

    rows = list(csv.DictReader(csv_path.open("r", encoding="utf-8")))
    assert rows == [
        {
            "timestamp": rows[0]["timestamp"],
            "event_timestamp": "2026-04-29T12:30:01+03:00",
            "provider": "telegram",
            "destination_id": "destination",
            "success": "true",
            "message": "sent",
        }
    ]


def test_notification_log_appends_without_duplicate_header(tmp_path: Path) -> None:
    """Notification logging should append subsequent rows."""

    csv_path = tmp_path / "logs" / "notifications.csv"

    append_notification_results(make_notification(), [make_result("telegram")], csv_path)
    append_notification_results(make_notification(), [make_result("email")], csv_path)

    lines = csv_path.read_text(encoding="utf-8").splitlines()
    rows = list(csv.DictReader(lines))
    assert lines[0] == "timestamp,event_timestamp,provider,destination_id,success,message"
    assert len(rows) == 2
    assert [row["provider"] for row in rows] == ["telegram", "email"]


def test_notification_log_failure_is_safe(monkeypatch, capsys) -> None:
    """Safe notification logging should report failures without raising."""

    def fake_append(notification, results, csv_path):
        raise OSError("disk full")

    monkeypatch.setattr("notifications.logging.append_notification_results", fake_append)

    safe_append_notification_results(make_notification(), [make_result()])

    assert "notification result log failed: OSError" in capsys.readouterr().err
