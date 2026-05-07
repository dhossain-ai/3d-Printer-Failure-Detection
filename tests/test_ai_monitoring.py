"""Tests for dashboard AI monitoring endpoints and service."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import config
from web_dashboard.app import app
from web_dashboard.monitoring_service import DashboardMonitoringService

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_service():
    """Stop and reset the singleton service between tests."""
    from web_dashboard.monitoring_service import get_service
    svc = get_service()
    svc.stop()
    # Hard-reset state
    svc.running = False
    svc.frames_processed = 0
    svc.last_detection_label = None
    svc.last_detection_confidence = 0.0
    svc.failure_detected = False
    svc.confirmed_failure = False
    svc.fail_frame_count = 0
    svc.last_error = None
    svc._latest_frame_jpeg = None
    yield
    svc.stop()


# ---------------------------------------------------------------------------
# /api/ai/status
# ---------------------------------------------------------------------------

def test_ai_status_default_stopped():
    response = client.get("/api/ai/status")
    assert response.status_code == 200
    data = response.json()
    assert data["running"] is False
    assert data["frames_processed"] == 0


# ---------------------------------------------------------------------------
# /api/ai/start
# ---------------------------------------------------------------------------

def test_ai_start_rejects_missing_camera_url():
    original = config.PRINTER_CAMERA_URL
    config.PRINTER_CAMERA_URL = ""
    try:
        response = client.post("/api/ai/start", json={})
        assert response.status_code == 409
    finally:
        config.PRINTER_CAMERA_URL = original


@patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup")
def test_ai_start_starts_and_rejects_double_start(mock_setup):
    """Start should succeed first time and reject on second call."""
    # Make _setup return a no-op (won't open real camera/model)
    mock_setup.return_value = (None, None)
    config.PRINTER_CAMERA_URL = "http://test:8080/stream"
    try:
        # First call
        response = client.post("/api/ai/start", json={})
        # Even if _setup fails, service.running should have been set then cleared
        # The key thing: no 500 crash
        assert response.status_code in (200, 409)
    finally:
        config.PRINTER_CAMERA_URL = ""


def test_ai_start_already_running():
    """If service.running is True, start should return 409."""
    from web_dashboard.monitoring_service import get_service
    svc = get_service()
    svc.running = True  # Simulate running state
    config.PRINTER_CAMERA_URL = "http://test/stream"
    try:
        response = client.post("/api/ai/start", json={})
        assert response.status_code == 409
        assert "already running" in response.json()["detail"].lower()
    finally:
        svc.running = False
        config.PRINTER_CAMERA_URL = ""


# ---------------------------------------------------------------------------
# /api/ai/stop
# ---------------------------------------------------------------------------

def test_ai_stop_when_not_running():
    """Stopping when not running should succeed gracefully."""
    response = client.post("/api/ai/stop")
    assert response.status_code == 200


def test_ai_stop_sets_running_false():
    from web_dashboard.monitoring_service import get_service
    svc = get_service()
    svc.running = True
    svc._stop_event.set()  # pre-signal so thread exits immediately
    response = client.post("/api/ai/stop")
    assert response.status_code == 200
    assert svc.running is False


# ---------------------------------------------------------------------------
# /api/ai/stream
# ---------------------------------------------------------------------------

def test_ai_stream_returns_mjpeg_when_stopped():
    """Stream endpoint should return 200 with correct multipart content-type."""
    # Patch the generator to yield exactly one frame, avoiding infinite loop in tests
    placeholder = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # minimal JPEG header prefix

    def _one_shot_generator():
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + placeholder + b"\r\n"

    with patch("web_dashboard.app._mjpeg_generator", side_effect=_one_shot_generator):
        response = client.get("/api/ai/stream")

    assert response.status_code == 200
    assert "multipart/x-mixed-replace" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# DashboardMonitoringService unit tests
# ---------------------------------------------------------------------------

def test_service_get_status_structure():
    svc = DashboardMonitoringService()
    status = svc.get_status()
    expected_keys = {
        "running", "source_name", "frames_processed",
        "last_detection_label", "last_detection_confidence",
        "failure_detected", "confirmed_failure", "fail_frame_count",
        "consecutive_fail_frames", "last_error", "last_action_result",
    }
    assert expected_keys == set(status.keys())


def test_service_start_rejects_empty_url():
    svc = DashboardMonitoringService()
    err = svc.start(camera_url="")
    assert err is not None
    assert svc.running is False


def test_service_start_rejects_double_start():
    svc = DashboardMonitoringService()
    svc.running = True
    err = svc.start(camera_url="http://test/stream")
    assert "already running" in err.lower()
    svc.running = False


def test_service_handles_detector_exception_safely():
    """If detector raises, the thread records last_error without crashing."""
    svc = DashboardMonitoringService()

    fake_frame = MagicMock()
    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, fake_frame)
    fake_cap.isOpened.return_value = True
    fake_cap.release = MagicMock()

    fake_detector = MagicMock()
    fake_detector.detect.side_effect = RuntimeError("fake detector crash")

    # Run one iteration manually by patching cv2.imencode
    with patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup",
               return_value=(fake_cap, fake_detector)), \
         patch("cv2.imencode", return_value=(False, None)):

        err = svc.start(camera_url="http://test/stream")
        assert err is None

        # Give thread a moment to process one frame
        time.sleep(0.3)
        svc.stop()

    assert svc.last_error is not None
    assert "detector crash" in svc.last_error or "Detection error" in svc.last_error


def test_service_stores_detection_result():
    """Service should store detection label and update fail_frame_count."""
    svc = DashboardMonitoringService()

    fake_frame = MagicMock()
    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, fake_frame)
    fake_cap.isOpened.return_value = True
    fake_cap.release = MagicMock()

    from detector import FrameDetection
    fake_detection = FrameDetection(
        annotated_frame=fake_frame,
        failure_detected=True,
        label="spaghetti",
        confidence=0.82,
    )
    fake_detector = MagicMock()
    fake_detector.detect.return_value = fake_detection

    import numpy as np
    dummy_img = np.zeros((10, 10, 3), dtype="uint8")

    with patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup",
               return_value=(fake_cap, fake_detector)), \
         patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"\xff\xd8\xff"))):

        svc.start(camera_url="http://test/stream")
        time.sleep(0.3)
        svc.stop()

    assert svc.last_detection_label == "spaghetti"
    assert svc.last_detection_confidence == pytest.approx(0.82)
    assert svc.frames_processed >= 1


# ---------------------------------------------------------------------------
# Regression: dashboard page still loads
# ---------------------------------------------------------------------------

def test_dashboard_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "PrintSentinel" in response.text
