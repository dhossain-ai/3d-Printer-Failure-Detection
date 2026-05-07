"""Screenshot eligibility helpers for notification providers."""

from pathlib import Path


def screenshot_within_limit(
    screenshot_path: Path | None,
    max_screenshot_mb: float,
) -> bool:
    """Return whether a screenshot exists and is within the configured size limit."""

    if screenshot_path is None:
        return False

    try:
        if not screenshot_path.exists() or not screenshot_path.is_file():
            return False
        if max_screenshot_mb <= 0:
            return False

        max_bytes = max_screenshot_mb * 1024 * 1024
        return screenshot_path.stat().st_size <= max_bytes
    except OSError:
        return False
