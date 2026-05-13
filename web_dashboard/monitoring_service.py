"""Background AI monitoring service for PrintSentinel dashboard.

This module manages a single background thread that reads camera frames,
runs YOLO detection, and stores annotated frames for MJPEG streaming.
It does NOT open an OpenCV window; the existing runner.py is unaffected.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from time import monotonic
from typing import Any

import config
from actions import trigger_printer_response
from utils import AlertCooldown

logger = logging.getLogger(__name__)

AI_ACTION_MODES = ("detection_only", "pause", "stop")


@dataclass(frozen=True)
class DashboardAiSettings:
    """Runtime AI tuning and safety controls for dashboard monitoring."""

    confidence_threshold: float = config.CONFIDENCE_THRESHOLD
    consecutive_fail_frames: int = config.CONSECUTIVE_FAIL_FRAMES
    alert_cooldown_seconds: int = config.ALERT_COOLDOWN_SECONDS
    auto_action_enabled: bool = False
    action_mode: str = "detection_only"


DEFAULT_DASHBOARD_AI_SETTINGS = DashboardAiSettings()


def normalize_ai_settings(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize a partial AI settings payload into scalar values."""

    raw = settings or {}
    return {
        "confidence_threshold": _coerce_float_or_original(
            raw.get(
                "confidence_threshold",
                DEFAULT_DASHBOARD_AI_SETTINGS.confidence_threshold,
            )
        ),
        "consecutive_fail_frames": _coerce_int_or_original(
            raw.get(
                "consecutive_fail_frames",
                DEFAULT_DASHBOARD_AI_SETTINGS.consecutive_fail_frames,
            )
        ),
        "alert_cooldown_seconds": _coerce_int_or_original(
            raw.get(
                "alert_cooldown_seconds",
                DEFAULT_DASHBOARD_AI_SETTINGS.alert_cooldown_seconds,
            )
        ),
        "auto_action_enabled": _coerce_bool(
            raw.get(
                "auto_action_enabled",
                DEFAULT_DASHBOARD_AI_SETTINGS.auto_action_enabled,
            )
        ),
        "action_mode": str(
            raw.get("action_mode", DEFAULT_DASHBOARD_AI_SETTINGS.action_mode)
        ).strip().lower(),
    }


def validate_ai_settings(settings: dict[str, Any] | None = None) -> list[str]:
    """Return validation errors for dashboard AI settings."""

    normalized = normalize_ai_settings(settings)
    errors: list[str] = []

    threshold = normalized["confidence_threshold"]
    if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
        errors.append("Confidence threshold must be between 0 and 1.")

    consecutive = normalized["consecutive_fail_frames"]
    if not isinstance(consecutive, int) or consecutive < 1:
        errors.append("Consecutive fail frames must be at least 1.")

    cooldown = normalized["alert_cooldown_seconds"]
    if not isinstance(cooldown, int) or cooldown < 0:
        errors.append("Alert cooldown seconds must be 0 or greater.")

    action_mode = normalized["action_mode"]
    if action_mode not in AI_ACTION_MODES:
        errors.append("Action mode must be detection_only, pause, or stop.")

    return errors


def build_ai_settings(settings: dict[str, Any] | None = None) -> DashboardAiSettings:
    """Build validated dashboard AI settings."""

    normalized = normalize_ai_settings(settings)
    errors = validate_ai_settings(normalized)
    if errors:
        raise ValueError("\n".join(errors))

    return DashboardAiSettings(
        confidence_threshold=float(normalized["confidence_threshold"]),
        consecutive_fail_frames=int(normalized["consecutive_fail_frames"]),
        alert_cooldown_seconds=int(normalized["alert_cooldown_seconds"]),
        auto_action_enabled=bool(normalized["auto_action_enabled"]),
        action_mode=str(normalized["action_mode"]),
    )


def serialize_ai_settings(settings: DashboardAiSettings) -> dict[str, Any]:
    """Return a JSON-safe AI settings payload."""

    return {
        "confidence_threshold": settings.confidence_threshold,
        "consecutive_fail_frames": settings.consecutive_fail_frames,
        "alert_cooldown_seconds": settings.alert_cooldown_seconds,
        "auto_action_enabled": settings.auto_action_enabled,
        "action_mode": settings.action_mode,
    }


class DashboardMonitoringService:
    """Manage the dashboard background AI monitoring thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._detector: Any | None = None
        self._settings = DEFAULT_DASHBOARD_AI_SETTINGS
        self._alert_cooldown = AlertCooldown(
            seconds=self._settings.alert_cooldown_seconds
        )

        # Shared state (protected by _lock for writes, read without lock for speed)
        self.running: bool = False
        self.source_name: str = ""
        self.frames_processed: int = 0
        self.last_detection_label: str | None = None
        self.last_detection_confidence: float = 0.0
        self.failure_detected: bool = False
        self.confirmed_failure: bool = False
        self.fail_frame_count: int = 0
        self.consecutive_fail_frames: int = self._settings.consecutive_fail_frames
        self.last_error: str | None = None
        self.last_action_result: str | None = None

        # Latest JPEG bytes for MJPEG stream
        self._latest_frame_jpeg: bytes | None = None

    def start(self, camera_url: str, camera_type: str = "stream") -> str | None:
        """Start the background monitoring thread."""

        with self._lock:
            if self.running:
                return "Monitoring is already running."
            if not camera_url.strip():
                return "Camera URL is not configured."

            self._reset_state_locked(camera_url)
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._monitoring_loop,
                args=(camera_url, camera_type),
                daemon=True,
                name="dashboard-monitoring",
            )
            self.running = True
            self._thread.start()
            return None

    def stop(self) -> None:
        """Signal the monitoring thread to stop and wait for it to exit."""

        with self._lock:
            if not self.running:
                return
            self._stop_event.set()

        thread = self._thread
        if thread is not None:
            thread.join(timeout=10)

        with self._lock:
            self.running = False
            self._detector = None

    def update_settings(self, incoming_settings: dict[str, Any]) -> dict[str, Any]:
        """Validate and apply runtime AI tuning settings."""

        updated_settings = build_ai_settings(incoming_settings)
        with self._lock:
            self._settings = updated_settings
            self.consecutive_fail_frames = updated_settings.consecutive_fail_frames
            self._alert_cooldown.seconds = updated_settings.alert_cooldown_seconds
            active_detector = self._detector

        if active_detector is not None and hasattr(active_detector, "_confidence_threshold"):
            active_detector._confidence_threshold = updated_settings.confidence_threshold

        return self.get_settings_payload()

    def get_settings_payload(self) -> dict[str, Any]:
        """Return current runtime settings plus effective auto-action state."""

        with self._lock:
            settings = self._settings
            running = self.running
            cooldown_remaining = self._alert_cooldown.remaining_seconds(monotonic())

        return {
            "settings": serialize_ai_settings(settings),
            "effective": self._build_effective_settings_payload(
                settings=settings,
                running=running,
                cooldown_remaining=cooldown_remaining,
            ),
        }

    def get_latest_frame_jpeg(self) -> bytes | None:
        """Return the latest JPEG-encoded annotated frame, or None."""

        return self._latest_frame_jpeg

    def get_status(self) -> dict[str, Any]:
        """Return a snapshot of the current monitoring state."""

        with self._lock:
            settings = self._settings
            cooldown_remaining = self._alert_cooldown.remaining_seconds(monotonic())

        effective = self._build_effective_settings_payload(
            settings=settings,
            running=self.running,
            cooldown_remaining=cooldown_remaining,
        )
        return {
            "running": self.running,
            "source_name": self.source_name,
            "frames_processed": self.frames_processed,
            "last_detection_label": self.last_detection_label,
            "last_detection_confidence": self.last_detection_confidence,
            "failure_detected": self.failure_detected,
            "confirmed_failure": self.confirmed_failure,
            "fail_frame_count": self.fail_frame_count,
            "consecutive_fail_frames": self.consecutive_fail_frames,
            "last_error": self.last_error,
            "last_action_result": self.last_action_result,
            "confidence_threshold": settings.confidence_threshold,
            "alert_cooldown_seconds": settings.alert_cooldown_seconds,
            "auto_action_enabled": settings.auto_action_enabled,
            "action_mode": settings.action_mode,
            "cooldown_remaining_seconds": cooldown_remaining,
            "printer_backend": effective["printer_backend"],
            "real_printer_command": effective["real_printer_command"],
            "auto_action_active": effective["auto_action_active"],
            "auto_action_reason": effective["auto_action_reason"],
        }

    def _monitoring_loop(self, camera_url: str, camera_type: str) -> None:
        """Background thread: open camera, run YOLO, store frames."""

        capture = None
        detector = None
        try:
            capture, detector = self._setup(camera_url, camera_type)
            if capture is None or detector is None:
                with self._lock:
                    self.running = False
                return

            self._run_loop(capture, detector)
        except Exception as exc:
            logger.error("Monitoring loop crashed: %s", exc)
            with self._lock:
                self.last_error = str(exc)
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
            with self._lock:
                self.running = False
                self._detector = None

    def _setup(self, camera_url: str, camera_type: str):
        """Open camera and load detector. Return `(capture, detector)` or `(None, None)`."""

        try:
            from sources import open_capture, printer_camera_source

            source = printer_camera_source(url=camera_url, camera_type=camera_type)
            capture, error = open_capture(source)
            if error:
                with self._lock:
                    self.last_error = f"Camera open failed: {error}"
                    self.running = False
                return None, None
        except Exception as exc:
            with self._lock:
                self.last_error = f"Camera setup failed: {exc}"
                self.running = False
            return None, None

        try:
            from detector import YoloFailureDetector

            with self._lock:
                confidence_threshold = self._settings.confidence_threshold

            detector = YoloFailureDetector(confidence_threshold=confidence_threshold)
            with self._lock:
                self._detector = detector
        except Exception as exc:
            with self._lock:
                self.last_error = f"Detector load failed: {exc}"
                self.running = False
                self._detector = None
            try:
                capture.release()
            except Exception:
                pass
            return None, None

        return capture, detector

    def _run_loop(self, capture: Any, detector: Any) -> None:
        """Main read-detect-store loop."""

        import cv2

        while not self._stop_event.is_set():
            ret, frame = capture.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            try:
                detection = detector.detect(frame)
                annotated = detection.annotated_frame
                now_seconds = monotonic()

                with self._lock:
                    current_settings = self._settings
                    self.frames_processed += 1
                    self.failure_detected = detection.failure_detected
                    if detection.failure_detected:
                        self.last_detection_label = detection.label
                        self.last_detection_confidence = detection.confidence
                        self.fail_frame_count += 1
                        self.confirmed_failure = (
                            self.fail_frame_count
                            >= current_settings.consecutive_fail_frames
                        )
                    else:
                        self.fail_frame_count = 0
                        self.confirmed_failure = False

                    should_trigger_auto_action = self._should_trigger_auto_action_locked(
                        confirmed_failure=self.confirmed_failure,
                        label=detection.label,
                        now_seconds=now_seconds,
                    )
                    if should_trigger_auto_action:
                        self._alert_cooldown.mark_triggered(now_seconds)

                if should_trigger_auto_action:
                    action_result = self._trigger_auto_action(current_settings.action_mode)
                    with self._lock:
                        self.last_action_result = action_result

                ret2, buf = cv2.imencode(
                    ".jpg",
                    annotated,
                    [cv2.IMWRITE_JPEG_QUALITY, 75],
                )
                if ret2:
                    self._latest_frame_jpeg = buf.tobytes()

            except Exception as exc:
                with self._lock:
                    self.last_error = f"Detection error: {exc}"
                logger.warning("Detection error on frame: %s", exc)

    def _should_trigger_auto_action_locked(
        self,
        confirmed_failure: bool,
        label: str | None,
        now_seconds: float,
    ) -> bool:
        """Return whether auto action should run for the current frame."""

        settings = self._settings
        return (
            confirmed_failure
            and label is not None
            and settings.auto_action_enabled
            and settings.action_mode != "detection_only"
            and self._alert_cooldown.is_ready(now_seconds)
        )

    def _trigger_auto_action(self, action_mode: str) -> str:
        """Run a guarded auto action or return a safe skip message."""

        effective = self._build_effective_settings_payload(
            settings=self._settings,
            running=self.running,
            cooldown_remaining=self._alert_cooldown.remaining_seconds(monotonic()),
        )
        if not effective["auto_action_active"]:
            return f"Auto action skipped: {effective['auto_action_reason']}"

        result = trigger_printer_response(action_mode)
        outcome = "success" if result.success else "failed"
        return f"Auto action {result.action}: {outcome} - {result.message}"

    def _build_effective_settings_payload(
        self,
        settings: DashboardAiSettings,
        running: bool,
        cooldown_remaining: int,
    ) -> dict[str, Any]:
        """Return effective runtime behavior for UI display."""

        backend = (config.PRINTER_BACKEND or "simulated").strip().lower()
        real_printer_command = backend != "simulated"

        if not settings.auto_action_enabled:
            auto_action_active = False
            auto_action_reason = "Auto action is disabled."
        elif settings.action_mode == "detection_only":
            auto_action_active = False
            auto_action_reason = "Action mode is detection_only."
        elif backend == "creality_ws" and not config.CREALITY_CONTROL_ENABLED:
            auto_action_active = False
            auto_action_reason = (
                "Creality control must be enabled before dashboard auto action can run."
            )
        elif backend == "creality_ws" and not config.CREALITY_WS_URL.strip():
            auto_action_active = False
            auto_action_reason = "CREALITY_WS_URL is not configured."
        elif backend == "http" and not config.PRINTER_BASE_URL.strip():
            auto_action_active = False
            auto_action_reason = "PRINTER_BASE_URL is not configured."
        elif real_printer_command:
            auto_action_active = True
            auto_action_reason = (
                f"Confirmed failures will send a real '{settings.action_mode}' command."
            )
        else:
            auto_action_active = True
            auto_action_reason = (
                f"Confirmed failures will run a simulated '{settings.action_mode}' action."
            )

        return {
            **serialize_ai_settings(settings),
            "running": running,
            "cooldown_remaining_seconds": cooldown_remaining,
            "printer_backend": backend,
            "real_printer_command": real_printer_command,
            "auto_action_active": auto_action_active,
            "auto_action_reason": auto_action_reason,
        }

    def _reset_state_locked(self, camera_url: str) -> None:
        """Reset counters and detection state (must be called with lock held)."""

        self.source_name = camera_url
        self.frames_processed = 0
        self.last_detection_label = None
        self.last_detection_confidence = 0.0
        self.failure_detected = False
        self.confirmed_failure = False
        self.fail_frame_count = 0
        self.consecutive_fail_frames = self._settings.consecutive_fail_frames
        self.last_error = None
        self.last_action_result = None
        self._latest_frame_jpeg = None
        self._alert_cooldown.last_triggered_at = None


def _coerce_bool(value: Any) -> bool:
    """Coerce common API boolean values."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_int_or_original(value: Any) -> int | Any:
    """Coerce a value to int, preserving invalid input for validation."""

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return value


def _coerce_float_or_original(value: Any) -> float | Any:
    """Coerce a value to float, preserving invalid input for validation."""

    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return value


_service = DashboardMonitoringService()


def get_service() -> DashboardMonitoringService:
    """Return the shared monitoring service singleton."""

    return _service
