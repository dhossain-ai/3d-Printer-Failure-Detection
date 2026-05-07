"""Application configuration for PrintSentinel."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


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

SIMULATED_ACTION = PRINTER_ACTION

NOTIFICATIONS_ENABLED = _env_bool("NOTIFICATIONS_ENABLED", False)
NOTIFICATION_TIMEOUT_SECONDS = _env_float("NOTIFICATION_TIMEOUT_SECONDS", 5.0)
WINDOWS_NOTIFICATIONS_ENABLED = _env_bool("WINDOWS_NOTIFICATIONS_ENABLED", False)
WINDOWS_NOTIFICATION_APP_NAME = _env_string(
    "WINDOWS_NOTIFICATION_APP_NAME",
    "PrintSentinel",
)
TELEGRAM_NOTIFICATIONS_ENABLED = _env_bool("TELEGRAM_NOTIFICATIONS_ENABLED", False)
TELEGRAM_BOT_TOKEN = _env_string("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _env_string("TELEGRAM_CHAT_ID", "")
TELEGRAM_SEND_SCREENSHOT = _env_bool("TELEGRAM_SEND_SCREENSHOT", True)
EMAIL_NOTIFICATIONS_ENABLED = _env_bool("EMAIL_NOTIFICATIONS_ENABLED", False)
SMTP_HOST = _env_string("SMTP_HOST", "")
SMTP_PORT = _env_int("SMTP_PORT", 465)
SMTP_SECURITY = _env_string("SMTP_SECURITY", "ssl")
SMTP_USERNAME = _env_string("SMTP_USERNAME", "")
SMTP_PASSWORD = _env_string("SMTP_PASSWORD", "")
EMAIL_FROM = _env_string("EMAIL_FROM", "")
EMAIL_TO = _env_string("EMAIL_TO", "")
EMAIL_SEND_SCREENSHOT = _env_bool("EMAIL_SEND_SCREENSHOT", True)

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
