"""Background AI monitoring service for PrintSentinel dashboard.

This module manages a single background thread that reads camera frames,
runs YOLO detection, and stores annotated frames for MJPEG streaming.
It does NOT open an OpenCV window; the existing runner.py is unaffected.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import config

logger = logging.getLogger(__name__)


class DashboardMonitoringService:
    """Manages one background AI monitoring thread for the dashboard.

    Only one thread may be running at once. Detection errors are recorded
    without crashing the server. Confirmed failures are detection-only in
    this phase; printer actions are not triggered to avoid double-firing
    alongside the OpenCV runner.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Shared state (protected by _lock for writes, read without lock for speed)
        self.running: bool = False
        self.source_name: str = ""
        self.frames_processed: int = 0
        self.last_detection_label: str | None = None
        self.last_detection_confidence: float = 0.0
        self.failure_detected: bool = False
        self.confirmed_failure: bool = False
        self.fail_frame_count: int = 0
        self.consecutive_fail_frames: int = config.CONSECUTIVE_FAIL_FRAMES
        self.last_error: str | None = None
        self.last_action_result: str | None = None

        # Latest JPEG bytes for MJPEG stream
        self._latest_frame_jpeg: bytes | None = None

    # ------------------------------------------------------------------
    # Public control API
    # ------------------------------------------------------------------

    def start(self, camera_url: str, camera_type: str = "stream") -> str | None:
        """Start the background monitoring thread.

        Returns None on success or an error message string on failure.
        Rejects if already running.
        """
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

    def get_latest_frame_jpeg(self) -> bytes | None:
        """Return the latest JPEG-encoded annotated frame, or None."""
        return self._latest_frame_jpeg

    def get_status(self) -> dict:
        """Return a snapshot of the current monitoring state."""
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
        }

    # ------------------------------------------------------------------
    # Internal monitoring loop
    # ------------------------------------------------------------------

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
            logger.error(f"Monitoring loop crashed: {exc}")
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

    def _setup(self, camera_url: str, camera_type: str):
        """Open camera and load detector. Return (capture, detector) or (None, None)."""
        try:
            from sources import printer_camera_source, open_capture
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
            detector = YoloFailureDetector()
        except Exception as exc:
            with self._lock:
                self.last_error = f"Detector load failed: {exc}"
                self.running = False
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

                # Update detection state
                with self._lock:
                    self.frames_processed += 1
                    self.failure_detected = detection.failure_detected
                    if detection.failure_detected:
                        self.last_detection_label = detection.label
                        self.last_detection_confidence = detection.confidence
                        self.fail_frame_count += 1
                        if self.fail_frame_count >= self.consecutive_fail_frames:
                            self.confirmed_failure = True
                    else:
                        self.fail_frame_count = 0
                        self.confirmed_failure = False

                # Encode to JPEG for MJPEG stream
                ret2, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret2:
                    self._latest_frame_jpeg = buf.tobytes()

            except Exception as exc:
                with self._lock:
                    self.last_error = f"Detection error: {exc}"
                logger.warning(f"Detection error on frame: {exc}")
                # Don't crash — keep running

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset_state_locked(self, camera_url: str) -> None:
        """Reset counters and detection state (must be called with lock held)."""
        self.source_name = camera_url
        self.frames_processed = 0
        self.last_detection_label = None
        self.last_detection_confidence = 0.0
        self.failure_detected = False
        self.confirmed_failure = False
        self.fail_frame_count = 0
        self.last_error = None
        self.last_action_result = None
        self._latest_frame_jpeg = None


# Module-level singleton used by app.py
_service = DashboardMonitoringService()


def get_service() -> DashboardMonitoringService:
    """Return the shared monitoring service singleton."""
    return _service
