"""Application configuration for PrintSentinel."""

import os
from pathlib import Path

from notifications.settings import load_notification_settings

BASE_DIR = Path(__file__).resolve().parent
_LOCAL_NOTIFICATION_SETTINGS = load_notification_settings()


def _env_value(name: str) -> str | None:
    """Return an explicitly configured environment variable value."""

    prefixed_name = f"PRINTSENTINEL_{name}"
    if prefixed_name in os.environ:
        return os.environ[prefixed_name]
    if name in os.environ:
        return os.environ[name]
    return None


def _env_string(name: str, default: str) -> str:
    """Return a stripped environment variable value or a default."""

    return os.getenv(f"PRINTSENTINEL_{name}", os.getenv(name, default)).strip()


def _env_float(name: str, default: float) -> float:
    """Return a float environment variable value or a safe default."""

    raw_value = _env_string(name, str(default))
    try:
        return float(raw_value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    """Return an integer environment variable value or a safe default."""

    raw_value = _env_string(name, str(default))
    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    """Return a boolean environment variable value or a safe default."""

    raw_value = _env_string(name, str(default)).lower()
    return _parse_bool(raw_value, default)


def _env_choice(name: str, default: str, allowed_values: tuple[str, ...]) -> str:
    """Return a lower-case environment choice or a safe default."""

    raw_value = _env_string(name, default).lower()
    if raw_value in allowed_values:
        return raw_value
    return default


def _notification_string(name: str, default: str) -> str:
    """Return notification config from env, then local settings, then default."""

    raw_value = _env_value(name)
    if raw_value is not None and raw_value.strip():
        return raw_value.strip()

    local_value = _LOCAL_NOTIFICATION_SETTINGS.get(name, default)
    if local_value is None:
        return default

    local_text = str(local_value).strip()
    return local_text if local_text else default


def _notification_float(name: str, default: float) -> float:
    """Return notification float config from env, then local settings."""

    raw_value = _env_value(name)
    if raw_value is not None and raw_value.strip():
        try:
            return float(raw_value)
        except ValueError:
            return default

    try:
        return float(_LOCAL_NOTIFICATION_SETTINGS.get(name, default))
    except (TypeError, ValueError):
        return default


def _notification_int(name: str, default: int) -> int:
    """Return notification integer config from env, then local settings."""

    raw_value = _env_value(name)
    if raw_value is not None and raw_value.strip():
        try:
            return int(raw_value)
        except ValueError:
            return default

    try:
        return int(_LOCAL_NOTIFICATION_SETTINGS.get(name, default))
    except (TypeError, ValueError):
        return default


def _notification_bool(name: str, default: bool) -> bool:
    """Return notification boolean config from env, then local settings."""

    raw_value = _env_value(name)
    if raw_value is not None and raw_value.strip():
        return _parse_bool(raw_value, default)

    return _parse_bool(_LOCAL_NOTIFICATION_SETTINGS.get(name, default), default)


def _parse_bool(value: object, default: bool) -> bool:
    """Parse common boolean config values."""

    raw_value = str(value).strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return default


MODEL_PATH = BASE_DIR / "models" / "model.pt"
SAMPLE_VIDEO_PATH = BASE_DIR / "assets" / "demo.mp4"
CAPTURES_DIR = BASE_DIR / "captures"
LOGS_DIR = BASE_DIR / "logs"
EVENTS_CSV_PATH = LOGS_DIR / "events.csv"

FAILURE_CLASSES = ("spaghetti", "stringing", "zits")
CONFIDENCE_THRESHOLD = 0.35
CONSECUTIVE_FAIL_FRAMES = 3
ALERT_COOLDOWN_SECONDS = 20
ALERT_BEEP_ENABLED = False

PRINTER_BACKEND = _env_string("PRINTER_BACKEND", "simulated")
PRINTER_ACTION = _env_string("PRINTER_ACTION", "stop")
PRINTER_BASE_URL = _env_string("PRINTER_BASE_URL", "")
PRINTER_STOP_ENDPOINT = _env_string("PRINTER_STOP_ENDPOINT", "/stop")
PRINTER_PAUSE_ENDPOINT = _env_string("PRINTER_PAUSE_ENDPOINT", "/pause")
PRINTER_HEALTH_ENDPOINT = _env_string("PRINTER_HEALTH_ENDPOINT", "/health")
PRINTER_REQUEST_TIMEOUT_SECONDS = _env_float("PRINTER_REQUEST_TIMEOUT_SECONDS", 3.0)
PRINTER_API_TOKEN = _env_string("PRINTER_API_TOKEN", "")
PRINTER_AUTH_HEADER_NAME = _env_string("PRINTER_AUTH_HEADER_NAME", "Authorization")
PRINTER_EXTRA_HEADERS_JSON = _env_string("PRINTER_EXTRA_HEADERS_JSON", "")
PRINTER_CAMERA_URL = _env_string("PRINTER_CAMERA_URL", "")
PRINTER_CAMERA_TYPE = _env_choice(
    "PRINTER_CAMERA_TYPE",
    "stream",
    ("stream", "snapshot"),
)

SIMULATED_ACTION = PRINTER_ACTION

NOTIFICATIONS_ENABLED = _notification_bool("NOTIFICATIONS_ENABLED", False)
NOTIFICATION_TIMEOUT_SECONDS = _notification_float(
    "NOTIFICATION_TIMEOUT_SECONDS",
    5.0,
)
WINDOWS_NOTIFICATIONS_ENABLED = _notification_bool(
    "WINDOWS_NOTIFICATIONS_ENABLED",
    False,
)
WINDOWS_NOTIFICATION_APP_NAME = _notification_string(
    "WINDOWS_NOTIFICATION_APP_NAME",
    "PrintSentinel",
)
TELEGRAM_NOTIFICATIONS_ENABLED = _notification_bool(
    "TELEGRAM_NOTIFICATIONS_ENABLED",
    False,
)
TELEGRAM_BOT_TOKEN = _notification_string("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _notification_string("TELEGRAM_CHAT_ID", "")
TELEGRAM_SEND_SCREENSHOT = _notification_bool("TELEGRAM_SEND_SCREENSHOT", True)
EMAIL_NOTIFICATIONS_ENABLED = _notification_bool(
    "EMAIL_NOTIFICATIONS_ENABLED",
    False,
)
SMTP_HOST = _notification_string("SMTP_HOST", "")
SMTP_PORT = _notification_int("SMTP_PORT", 465)
SMTP_SECURITY = _notification_string("SMTP_SECURITY", "ssl")
SMTP_USERNAME = _notification_string("SMTP_USERNAME", "")
SMTP_PASSWORD = _notification_string("SMTP_PASSWORD", "")
EMAIL_FROM = _notification_string("EMAIL_FROM", "")
EMAIL_TO = _notification_string("EMAIL_TO", "")
EMAIL_SEND_SCREENSHOT = _notification_bool("EMAIL_SEND_SCREENSHOT", True)
NOTIFICATION_MAX_SCREENSHOT_MB = _notification_float(
    "NOTIFICATION_MAX_SCREENSHOT_MB",
    5.0,
)

WINDOW_NAME = "PrintSentinel"
STATUS_MONITORING = "STATUS: MONITORING"
STATUS_FAIL_DETECTED = "STATUS: FAIL DETECTED -> STOP PRINTER"
STATUS_CONFIRMING = "STATUS: CHECKING"

OVERLAY_HEIGHT = 150
OVERLAY_PADDING = 16
OVERLAY_LINE_HEIGHT = 23
OVERLAY_FONT_SCALE = 0.55
OVERLAY_TITLE_FONT_SCALE = 0.75
OVERLAY_THICKNESS = 1
OVERLAY_TITLE_THICKNESS = 2

COLOR_STATUS_OK = (0, 150, 0)
COLOR_STATUS_FAIL = (0, 0, 220)
COLOR_STATUS_CHECKING = (0, 140, 220)
COLOR_OVERLAY_BACKGROUND = (28, 28, 28)
COLOR_STATUS_TEXT = (255, 255, 255)
COLOR_STATUS_DETAIL = (235, 235, 235)
