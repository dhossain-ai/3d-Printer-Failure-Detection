"""Application configuration for PrintSentinel Phase 1."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "models" / "model.pt"
SAMPLE_VIDEO_PATH = BASE_DIR / "assets" / "demo.mp4"
CAPTURES_DIR = BASE_DIR / "captures"
LOGS_DIR = BASE_DIR / "logs"
EVENTS_LOG_PATH = LOGS_DIR / "events.csv"

FAILURE_CLASSES = ("spaghetti", "stringing", "zits")
CONFIDENCE_THRESHOLD = 0.35
CONSECUTIVE_FAIL_FRAMES = 3

WINDOW_NAME = "PrintSentinel"
STATUS_MONITORING = "STATUS: MONITORING"
STATUS_FAIL_DETECTED = "STATUS: FAIL DETECTED -> STOP PRINTER"

STATUS_BAR_HEIGHT = 72
STATUS_TEXT_ORIGIN = (20, 44)
STATUS_DETAIL_ORIGIN = (20, 64)

COLOR_STATUS_OK = (0, 150, 0)
COLOR_STATUS_FAIL = (0, 0, 220)
COLOR_STATUS_TEXT = (255, 255, 255)
COLOR_STATUS_DETAIL = (235, 235, 235)
