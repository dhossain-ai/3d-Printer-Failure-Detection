"""CSV logging for notification results."""

import csv
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from notifications.models import FailureNotification, NotificationResult

BASE_DIR = Path(__file__).resolve().parents[1]
NOTIFICATIONS_CSV_PATH = BASE_DIR / "logs" / "notifications.csv"

NOTIFICATION_LOG_COLUMNS = (
    "timestamp",
    "event_timestamp",
    "provider",
    "destination_id",
    "success",
    "message",
)


def append_notification_results(
    notification: FailureNotification,
    results: Iterable[NotificationResult],
    csv_path: Path = NOTIFICATIONS_CSV_PATH,
) -> None:
    """Append notification provider results to the CSV log."""

    result_rows = list(results)
    if not result_rows:
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    logged_at = datetime.now().isoformat(timespec="seconds")

    with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=NOTIFICATION_LOG_COLUMNS)
        if should_write_header:
            writer.writeheader()

        for result in result_rows:
            writer.writerow(
                {
                    "timestamp": logged_at,
                    "event_timestamp": notification.timestamp,
                    "provider": result.provider,
                    "destination_id": result.destination_id,
                    "success": str(result.success).lower(),
                    "message": result.message,
                }
            )


def safe_append_notification_results(
    notification: FailureNotification,
    results: Iterable[NotificationResult],
    csv_path: Path = NOTIFICATIONS_CSV_PATH,
) -> None:
    """Append notification results without allowing logging errors to escape."""

    try:
        append_notification_results(notification, results, csv_path=csv_path)
    except Exception as exc:  # noqa: BLE001 - logging must not crash monitoring.
        print(
            (
                "PRINTSENTINEL WARNING: notification result log failed: "
                f"{exc.__class__.__name__}"
            ),
            file=sys.stderr,
        )
