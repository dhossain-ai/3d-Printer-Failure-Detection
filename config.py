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

SIMULATED_ACTION = PRINTER_ACTION

WINDOW_NAME = "PrintSentinel"
STATUS_MONITORING = "STATUS: MONITORING"
STATUS_FAIL_DETECTED = "STATUS: FAIL DETECTED -> STOP PRINTER"
STATUS_CONFIRMING = "STATUS: CHECKING"

OVERLAY_HEIGHT = 128
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
