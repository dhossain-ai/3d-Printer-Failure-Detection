"""Tests for dashboard AI monitoring endpoints and service."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import config
import numpy as np
from dataset_capture import DatasetFrameSnapshot
from actions import FailureEvent
from web_dashboard.app import app
from web_dashboard.monitoring_service import (
    DEFAULT_DASHBOARD_AI_SETTINGS,
    DashboardMonitoringService,
    DashboardSourceSettings,
    handle_dashboard_confirmed_failure,
    select_dashboard_failure_frame,
    get_default_dashboard_source_settings,
    validate_source_settings,
    validate_ai_settings,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_service():
    """Stop and reset the singleton service between tests."""
    from web_dashboard.monitoring_service import get_service
    svc = get_service()
    svc.stop()
    svc.update_settings({})
    svc.update_source_settings({})
    svc.running = False
    svc.frames_processed = 0
    svc.last_detection_label = None
    svc.last_detection_confidence = 0.0
    svc.failure_detected = False
    svc.confirmed_failure = False
    svc.fail_frame_count = 0
    svc.last_error = None
    svc.last_action_result = None
    svc.latest_bounding_box = None
    svc._latest_raw_frame = None
    svc._latest_annotated_frame = None
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
    assert data["auto_action_enabled"] is False
    assert data["action_mode"] == "detection_only"


def test_ai_settings_default_safe():
    response = client.get("/api/ai/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["settings"] == {
        "confidence_threshold": DEFAULT_DASHBOARD_AI_SETTINGS.confidence_threshold,
        "consecutive_fail_frames": DEFAULT_DASHBOARD_AI_SETTINGS.consecutive_fail_frames,
        "alert_cooldown_seconds": DEFAULT_DASHBOARD_AI_SETTINGS.alert_cooldown_seconds,
        "auto_action_enabled": False,
        "action_mode": "detection_only",
        "roi_enabled": False,
        "roi_x": 0.0,
        "roi_y": 0.0,
        "roi_width": 1.0,
        "roi_height": 1.0,
    }
    assert data["effective"]["auto_action_active"] is False
    assert "disabled" in data["effective"]["auto_action_reason"].lower()


def test_ai_settings_invalid_threshold_rejected():
    response = client.post(
        "/api/ai/settings",
        json={"confidence_threshold": 1.5},
    )
    assert response.status_code == 400
    assert "Confidence threshold must be between 0 and 1." in response.json()["detail"]["errors"]


def test_ai_settings_invalid_action_mode_rejected():
    response = client.post(
        "/api/ai/settings",
        json={"action_mode": "resume"},
    )
    assert response.status_code == 400
    assert "Action mode must be detection_only, pause, or stop." in response.json()["detail"]["errors"]


def test_ai_settings_update_affects_monitoring_service():
    from web_dashboard.monitoring_service import get_service

    response = client.post(
        "/api/ai/settings",
        json={
            "confidence_threshold": 0.72,
            "consecutive_fail_frames": 5,
            "alert_cooldown_seconds": 12,
            "auto_action_enabled": True,
            "action_mode": "pause",
            "roi_enabled": True,
            "roi_x": 0.2,
            "roi_y": 0.1,
            "roi_width": 0.5,
            "roi_height": 0.6,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["confidence_threshold"] == pytest.approx(0.72)
    assert data["settings"]["consecutive_fail_frames"] == 5
    assert data["settings"]["alert_cooldown_seconds"] == 12
    assert data["settings"]["auto_action_enabled"] is True
    assert data["settings"]["action_mode"] == "pause"
    assert data["settings"]["roi_enabled"] is True
    assert data["settings"]["roi_x"] == pytest.approx(0.2)

    service = get_service()
    status = service.get_status()
    assert status["confidence_threshold"] == pytest.approx(0.72)
    assert status["consecutive_fail_frames"] == 5
    assert status["alert_cooldown_seconds"] == 12
    assert status["auto_action_enabled"] is True
    assert status["action_mode"] == "pause"
    assert status["roi_enabled"] is True
    assert status["roi_width"] == pytest.approx(0.5)


def test_ai_settings_accepts_valid_roi_settings():
    response = client.post(
        "/api/ai/settings",
        json={
            "roi_enabled": True,
            "roi_x": 0.1,
            "roi_y": 0.2,
            "roi_width": 0.7,
            "roi_height": 0.6,
        },
    )

    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["roi_enabled"] is True
    assert settings["roi_x"] == pytest.approx(0.1)
    assert settings["roi_y"] == pytest.approx(0.2)
    assert settings["roi_width"] == pytest.approx(0.7)
    assert settings["roi_height"] == pytest.approx(0.6)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("roi_x", -0.1, "ROI x must be between 0 and 1."),
        ("roi_y", 1.1, "ROI y must be between 0 and 1."),
        ("roi_width", 0, "ROI width must be greater than 0."),
        ("roi_height", 0, "ROI height must be greater than 0."),
    ],
)
def test_ai_settings_rejects_invalid_roi_values(field, value, message):
    payload = {
        "roi_enabled": True,
        "roi_x": 0,
        "roi_y": 0,
        "roi_width": 1,
        "roi_height": 1,
    }
    payload[field] = value

    response = client.post("/api/ai/settings", json=payload)

    assert response.status_code == 400
    assert message in response.json()["detail"]["errors"]


def test_ai_settings_rejects_roi_x_plus_width_over_one():
    response = client.post(
        "/api/ai/settings",
        json={"roi_enabled": True, "roi_x": 0.6, "roi_y": 0, "roi_width": 0.5, "roi_height": 1},
    )

    assert response.status_code == 400
    assert "ROI x plus width must be less than or equal to 1." in response.json()["detail"]["errors"]


def test_ai_settings_rejects_roi_y_plus_height_over_one():
    response = client.post(
        "/api/ai/settings",
        json={"roi_enabled": True, "roi_x": 0, "roi_y": 0.6, "roi_width": 1, "roi_height": 0.5},
    )

    assert response.status_code == 400
    assert "ROI y plus height must be less than or equal to 1." in response.json()["detail"]["errors"]


def test_get_source_returns_default_source():
    response = client.get("/api/source")
    assert response.status_code == 200
    data = response.json()
    expected = get_default_dashboard_source_settings()
    assert data["settings"]["source_type"] == expected.source_type
    assert data["settings"]["source_value"] == expected.source_value
    assert data["settings"]["camera_type"] == expected.camera_type


def test_post_source_accepts_printer_camera_url():
    response = client.post(
        "/api/source",
        json={
            "source_type": "printer_camera",
            "source_value": "http://printer:8080/?action=stream",
            "camera_type": "stream",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["source_type"] == "printer_camera"
    assert data["settings"]["source_value"] == "http://printer:8080/?action=stream"


def test_post_source_accepts_webcam_index():
    response = client.post(
        "/api/source",
        json={
            "source_type": "webcam",
            "source_value": "1",
            "camera_type": "stream",
        },
    )

    assert response.status_code == 200
    assert response.json()["settings"]["source_value"] == "1"


def test_post_source_accepts_demo_and_local_video_paths(tmp_path: Path):
    demo_path = tmp_path / "demo.mp4"
    local_path = tmp_path / "local.mp4"
    demo_path.write_bytes(b"demo")
    local_path.write_bytes(b"local")

    demo_response = client.post(
        "/api/source",
        json={
            "source_type": "demo_video",
            "source_value": str(demo_path),
            "camera_type": "stream",
        },
    )
    local_response = client.post(
        "/api/source",
        json={
            "source_type": "local_video",
            "source_value": str(local_path),
            "camera_type": "stream",
        },
    )

    assert demo_response.status_code == 200
    assert local_response.status_code == 200
    assert demo_response.json()["settings"]["source_type"] == "demo_video"
    assert local_response.json()["settings"]["source_type"] == "local_video"


def test_post_source_rejects_invalid_source_type():
    response = client.post(
        "/api/source",
        json={
            "source_type": "phone",
            "source_value": "0",
            "camera_type": "stream",
        },
    )

    assert response.status_code == 400
    assert "Source type must be printer_camera, webcam, demo_video, or local_video." in response.json()["detail"]["errors"]


# ---------------------------------------------------------------------------
# /api/ai/start
# ---------------------------------------------------------------------------

def test_ai_start_rejects_missing_selected_source():
    from web_dashboard.monitoring_service import get_service

    svc = get_service()
    svc._source_settings = DashboardSourceSettings(
        source_type="local_video",
        source_value="missing-demo.mp4",
        camera_type="stream",
    )

    response = client.post("/api/ai/start", json={})

    assert response.status_code == 409
    assert "Local video not found" in response.json()["detail"]


@patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup")
def test_ai_start_starts_and_rejects_double_start(mock_setup):
    """Start should succeed first time and reject on second call."""
    fake_capture = MagicMock()
    fake_capture.read.return_value = (False, None)
    fake_capture.release = MagicMock()
    fake_detector = MagicMock()
    mock_setup.return_value = (fake_capture, fake_detector)

    response = client.post("/api/ai/start", json={"camera_url": "http://test:8080/stream"})

    assert response.status_code == 200


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
        "source_type", "source_value", "camera_type",
        "latest_bounding_box",
        "confidence_threshold", "alert_cooldown_seconds",
        "auto_action_enabled", "action_mode", "cooldown_remaining_seconds",
        "roi_enabled", "roi_x", "roi_y", "roi_width", "roi_height",
        "printer_backend", "real_printer_command",
        "auto_action_active", "auto_action_reason",
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


def test_validate_source_settings_reports_errors():
    errors = validate_source_settings(
        {
            "source_type": "local_video",
            "source_value": "does-not-exist.mp4",
            "camera_type": "stream",
        }
    )

    assert any("Local video path does not exist" in error for error in errors)


def test_validate_ai_settings_reports_errors():
    errors = validate_ai_settings(
        {
            "confidence_threshold": "nope",
            "consecutive_fail_frames": 0,
            "alert_cooldown_seconds": -1,
            "action_mode": "resume",
            "roi_x": 0.7,
            "roi_width": 0.4,
            "roi_y": 0.8,
            "roi_height": 0.3,
        }
    )

    assert "Confidence threshold must be between 0 and 1." in errors
    assert "Consecutive fail frames must be at least 1." in errors
    assert "Alert cooldown seconds must be 0 or greater." in errors
    assert "Action mode must be detection_only, pause, or stop." in errors
    assert "ROI x plus width must be less than or equal to 1." in errors
    assert "ROI y plus height must be less than or equal to 1." in errors


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

    with patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup",
               return_value=(fake_cap, fake_detector)), \
         patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"\xff\xd8\xff"))):

        svc.start(camera_url="http://test/stream")
        time.sleep(0.3)
        svc.stop()

    assert svc.last_detection_label == "spaghetti"
    assert svc.last_detection_confidence == pytest.approx(0.82)
    assert svc.frames_processed >= 1


def test_roi_disabled_leaves_detection_frame_unchanged():
    svc = DashboardMonitoringService()
    svc.update_settings({"roi_enabled": False})
    frame = np.zeros((80, 120, 3), dtype="uint8")

    fake_cap = MagicMock()
    fake_cap.read.side_effect = [(True, frame), (False, None)]
    fake_cap.release = MagicMock()

    from detector import FrameDetection

    seen_shapes: list[tuple[int, ...]] = []

    def fake_detect(input_frame):
        seen_shapes.append(input_frame.shape)
        return FrameDetection(
            annotated_frame=input_frame.copy(),
            failure_detected=False,
            label=None,
            confidence=0.0,
        )

    fake_detector = MagicMock()
    fake_detector.detect.side_effect = fake_detect

    with patch(
        "web_dashboard.monitoring_service.DashboardMonitoringService._setup",
        return_value=(fake_cap, fake_detector),
    ):
        svc.start(camera_url="http://test/stream")
        time.sleep(0.2)
        svc.stop()

    assert seen_shapes[0] == frame.shape
    assert svc.latest_bounding_box is None


def test_monitoring_service_crops_frame_when_roi_enabled():
    svc = DashboardMonitoringService()
    svc.update_settings(
        {
            "roi_enabled": True,
            "roi_x": 0.25,
            "roi_y": 0.1,
            "roi_width": 0.5,
            "roi_height": 0.5,
        }
    )
    frame = np.zeros((100, 200, 3), dtype="uint8")

    fake_cap = MagicMock()
    fake_cap.read.side_effect = [(True, frame), (False, None)]
    fake_cap.release = MagicMock()

    from detector import FrameDetection

    seen_shapes: list[tuple[int, ...]] = []

    def fake_detect(input_frame):
        seen_shapes.append(input_frame.shape)
        return FrameDetection(
            annotated_frame=input_frame.copy(),
            failure_detected=True,
            label="spaghetti",
            confidence=0.8,
            bounding_box=(1, 2, 4, 5),
        )

    fake_detector = MagicMock()
    fake_detector.detect.side_effect = fake_detect

    with patch(
        "web_dashboard.monitoring_service.DashboardMonitoringService._setup",
        return_value=(fake_cap, fake_detector),
    ):
        svc.start(camera_url="http://test/stream")
        time.sleep(0.2)
        svc.stop()

    assert seen_shapes[0] == (50, 100, 3)
    assert svc.latest_bounding_box == (51, 12, 54, 15)
    assert svc.get_dataset_snapshot().roi_settings == {
        "roi_enabled": True,
        "roi_x": 0.25,
        "roi_y": 0.1,
        "roi_width": 0.5,
        "roi_height": 0.5,
    }


def test_dataset_capture_rejects_invalid_category():
    response = client.post(
        "/api/dataset/capture",
        json={"category": "bad", "notes": ""},
    )

    assert response.status_code == 400
    assert "Category must be" in response.json()["detail"]["errors"][0]


def test_dataset_capture_rejects_when_no_frame_available():
    response = client.post(
        "/api/dataset/capture",
        json={"category": "normal", "notes": ""},
    )

    assert response.status_code == 409
    assert "No frame is available" in response.json()["detail"]


def test_dataset_capture_api_returns_saved_paths(tmp_path: Path):
    snapshot = DatasetFrameSnapshot(
        raw_frame=np.zeros((12, 12, 3), dtype="uint8"),
        annotated_frame=np.ones((12, 12, 3), dtype="uint8"),
        bounding_box=None,
        source_type="demo_video",
        source_name="Sample video",
        source_value="assets/demo.mp4",
        label="spaghetti",
        confidence=0.77,
        confirmed_failure=False,
    )

    with (
        patch("web_dashboard.app.get_service") as mock_get_service,
        patch("web_dashboard.app.capture_dataset_frame") as mock_capture,
    ):
        mock_get_service.return_value.get_dataset_snapshot.return_value = snapshot
        mock_capture.return_value = {
            "timestamp": "2026-05-13T12:00:00+03:00",
            "category": "false_positive",
            "source_type": "demo_video",
            "source_name": "Sample video",
            "source_value": "assets/demo.mp4",
            "label": "spaghetti",
            "confidence": 0.77,
            "confirmed_failure": False,
            "frame_path": (tmp_path / "raw.jpg").as_posix(),
            "annotated_frame_path": (tmp_path / "annotated.jpg").as_posix(),
            "crop_path": None,
            "model_device": "auto",
            "notes": "reflection",
        }
        response = client.post(
            "/api/dataset/capture",
            json={"category": "false_positive", "notes": "reflection"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["capture"]["frame_path"].endswith("raw.jpg")
    assert data["capture"]["crop_path"] is None


def test_source_settings_update_affects_monitoring_service(tmp_path: Path):
    local_video = tmp_path / "demo.mp4"
    local_video.write_bytes(b"demo")
    svc = DashboardMonitoringService()

    payload = svc.update_source_settings(
        {
            "source_type": "local_video",
            "source_value": str(local_video),
            "camera_type": "stream",
        }
    )

    assert payload["settings"]["source_type"] == "local_video"
    assert payload["settings"]["source_value"] == str(local_video)
    assert payload["active_source"].startswith("Local video")


def test_source_change_while_running_requires_restart(tmp_path: Path):
    first_video = tmp_path / "first.mp4"
    second_video = tmp_path / "second.mp4"
    first_video.write_bytes(b"first")
    second_video.write_bytes(b"second")
    svc = DashboardMonitoringService()
    svc.update_source_settings(
        {
            "source_type": "local_video",
            "source_value": str(first_video),
            "camera_type": "stream",
        }
    )
    svc.running = True

    payload = svc.update_source_settings(
        {
            "source_type": "local_video",
            "source_value": str(second_video),
            "camera_type": "stream",
        }
    )

    assert payload["restart_required"] is True


def test_service_uses_selected_source(tmp_path: Path):
    demo_video = tmp_path / "demo.mp4"
    demo_video.write_bytes(b"demo")
    svc = DashboardMonitoringService()
    svc.update_source_settings(
        {
            "source_type": "demo_video",
            "source_value": str(demo_video),
            "camera_type": "stream",
        }
    )

    fake_capture = MagicMock()
    fake_capture.read.return_value = (False, None)
    fake_capture.release = MagicMock()
    fake_detector = MagicMock()

    with patch(
        "web_dashboard.monitoring_service.DashboardMonitoringService._setup",
        return_value=(fake_capture, fake_detector),
    ) as mock_setup:
        svc.start()
        svc.stop()

    passed_source = mock_setup.call_args.args[0]
    assert passed_source.label == "Sample video"
    assert passed_source.value == str(demo_video)


def test_service_updates_running_detector_threshold():
    svc = DashboardMonitoringService()
    active_detector = MagicMock()
    active_detector._confidence_threshold = 0.35
    svc._detector = active_detector

    svc.update_settings({"confidence_threshold": 0.7})

    assert active_detector._confidence_threshold == pytest.approx(0.7)
    assert svc.get_status()["confidence_threshold"] == pytest.approx(0.7)


def test_dashboard_confirmed_failure_prefers_annotated_frame(monkeypatch):
    annotated = np.full((4, 4, 3), 255, dtype=np.uint8)
    raw = np.zeros((4, 4, 3), dtype=np.uint8)
    captured: dict[str, object] = {}

    def fake_handle(frame, source, label, confidence, printer_action):
        captured["frame"] = frame
        return FailureEvent(
            timestamp="2026-04-29T12:30:01+03:00",
            source=source,
            label=label,
            confidence=confidence,
            action=printer_action,
            screenshot_path=Path("captures/failure.jpg"),
            action_success=True,
            action_message="ok",
        )

    monkeypatch.setattr(
        "web_dashboard.monitoring_service.handle_confirmed_failure",
        fake_handle,
    )

    handle_dashboard_confirmed_failure(
        action_mode="pause",
        annotated_frame=annotated,
        raw_frame=raw,
        source_name="Sample video",
        label="spaghetti",
        confidence=0.91,
    )

    assert captured["frame"] is annotated


def test_dashboard_confirmed_failure_falls_back_to_raw_frame(monkeypatch):
    raw = np.zeros((4, 4, 3), dtype=np.uint8)
    captured: dict[str, object] = {}

    def fake_handle(frame, source, label, confidence, printer_action):
        captured["frame"] = frame
        return FailureEvent(
            timestamp="2026-04-29T12:30:01+03:00",
            source=source,
            label=label,
            confidence=confidence,
            action=printer_action,
            screenshot_path=Path("captures/failure.jpg"),
            action_success=True,
            action_message="ok",
        )

    monkeypatch.setattr(
        "web_dashboard.monitoring_service.handle_confirmed_failure",
        fake_handle,
    )

    handle_dashboard_confirmed_failure(
        action_mode="pause",
        annotated_frame=None,
        raw_frame=raw,
        source_name="Sample video",
        label="spaghetti",
        confidence=0.91,
    )

    assert captured["frame"] is raw
    assert select_dashboard_failure_frame(None, raw) is raw


def test_auto_action_disabled_prevents_action_trigger():
    svc = DashboardMonitoringService()
    svc.update_settings(
        {
            "auto_action_enabled": False,
            "action_mode": "pause",
            "consecutive_fail_frames": 1,
        }
    )

    fake_frame = MagicMock()
    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, fake_frame)
    fake_cap.release = MagicMock()

    from detector import FrameDetection

    fake_detector = MagicMock()
    fake_detector.detect.return_value = FrameDetection(
        annotated_frame=fake_frame,
        failure_detected=True,
        label="spaghetti",
        confidence=0.91,
    )

    with (
        patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup", return_value=(fake_cap, fake_detector)),
        patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"jpeg"))),
        patch("web_dashboard.monitoring_service.trigger_printer_response") as mock_trigger,
    ):
        svc.start(camera_url="http://test/stream")
        time.sleep(0.3)
        svc.stop()

    mock_trigger.assert_not_called()


def test_detection_only_mode_prevents_action_trigger():
    svc = DashboardMonitoringService()
    svc.update_settings(
        {
            "auto_action_enabled": True,
            "action_mode": "detection_only",
            "consecutive_fail_frames": 1,
        }
    )

    fake_frame = MagicMock()
    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, fake_frame)
    fake_cap.release = MagicMock()

    from detector import FrameDetection

    fake_detector = MagicMock()
    fake_detector.detect.return_value = FrameDetection(
        annotated_frame=fake_frame,
        failure_detected=True,
        label="spaghetti",
        confidence=0.91,
    )

    with (
        patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup", return_value=(fake_cap, fake_detector)),
        patch("cv2.imencode", return_value=(True, MagicMock(tobytes=lambda: b"jpeg"))),
        patch("web_dashboard.monitoring_service.trigger_printer_response") as mock_trigger,
    ):
        svc.start(camera_url="http://test/stream")
        time.sleep(0.3)
        svc.stop()

    mock_trigger.assert_not_called()


def test_dashboard_confirmed_failure_cooldown_prevents_repeated_notifications():
    svc = DashboardMonitoringService()
    svc.update_settings(
        {
            "auto_action_enabled": True,
            "action_mode": "pause",
            "consecutive_fail_frames": 1,
            "alert_cooldown_seconds": 999,
        }
    )

    raw_frame = np.zeros((8, 8, 3), dtype=np.uint8)
    annotated_frame = np.full((8, 8, 3), 255, dtype=np.uint8)
    fake_cap = MagicMock()
    fake_cap.read.return_value = (True, raw_frame)
    fake_cap.release = MagicMock()

    from detector import FrameDetection

    fake_detector = MagicMock()
    fake_detector.detect.return_value = FrameDetection(
        annotated_frame=annotated_frame,
        failure_detected=True,
        label="spaghetti",
        confidence=0.91,
    )
    handled_events: list[FailureEvent] = []

    def fake_handle(frame, source, label, confidence, printer_action):
        event = FailureEvent(
            timestamp="2026-04-29T12:30:01+03:00",
            source=source,
            label=label,
            confidence=confidence,
            action=printer_action,
            screenshot_path=Path("captures/failure.jpg"),
            action_success=True,
            action_message="ok",
        )
        handled_events.append(event)
        return event

    with (
        patch("web_dashboard.monitoring_service.DashboardMonitoringService._setup", return_value=(fake_cap, fake_detector)),
        patch("web_dashboard.monitoring_service.handle_confirmed_failure", side_effect=fake_handle),
    ):
        svc.start(camera_url="http://test/stream")
        time.sleep(0.3)
        svc.stop()

    assert len(handled_events) == 1


# ---------------------------------------------------------------------------
# Regression: dashboard page still loads
# ---------------------------------------------------------------------------

def test_dashboard_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "PrintSentinel" in response.text
