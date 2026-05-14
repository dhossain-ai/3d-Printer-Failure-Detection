"""Screenshot eligibility helpers for notification providers."""

from pathlib import Path


def screenshot_within_limit(
    screenshot_path: Path | None,
    max_screenshot_mb: float,
) -> bool:
    """Return whether a screenshot exists and is within the configured size limit."""

    return screenshot_unavailable_reason(screenshot_path, max_screenshot_mb) is None


def screenshot_unavailable_reason(
    screenshot_path: Path | None,
    max_screenshot_mb: float,
) -> str | None:
    """Return why a screenshot cannot be attached, or None when it can."""

    if screenshot_path is None:
        return "screenshot path is not available"

    try:
        if not screenshot_path.exists() or not screenshot_path.is_file():
            return "screenshot file is missing"
        if max_screenshot_mb <= 0:
            return "screenshot size limit is disabled"

        max_bytes = max_screenshot_mb * 1024 * 1024
        if screenshot_path.stat().st_size > max_bytes:
            return "screenshot exceeds configured size limit"
    except OSError as exc:
        return f"screenshot could not be checked: {exc.__class__.__name__}"

    return None
