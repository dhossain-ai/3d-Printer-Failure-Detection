"""OpenCV monitoring loop for PrintSentinel."""

import sys
from time import monotonic
from typing import Any

from actions import handle_confirmed_failure
from annotator import OverlayState, draw_monitoring_overlay
from config import (
    ALERT_COOLDOWN_SECONDS,
    CONSECUTIVE_FAIL_FRAMES,
    PRINTER_ACTION,
    PRINTER_BACKEND,
    WINDOW_NAME,
)
from detector import YoloFailureDetector
from printer_controller import normalize_printer_action
from session_summary import SessionSummary, print_session_start, print_session_summary
from sources import VideoSource, open_capture
from utils import AlertCooldown


class PrintSentinelRunner:
    """Run detection against a selected video source."""

    def __init__(
        self,
        detector: YoloFailureDetector,
        consecutive_fail_frames: int = CONSECUTIVE_FAIL_FRAMES,
        alert_cooldown_seconds: int = ALERT_COOLDOWN_SECONDS,
    ) -> None:
        """Create a runner with a detector and confirmation threshold."""

        self._detector = detector
        self._consecutive_fail_frames = consecutive_fail_frames
        self._alert_cooldown = AlertCooldown(alert_cooldown_seconds)

    def run(self, source: VideoSource) -> str | None:
        """Run the monitoring loop and return an error message if startup fails."""

        capture, error = open_capture(source)
        if error is not None or capture is None:
            return error

        fail_frame_count = 0
        latest_failure_label: str | None = None
        latest_failure_confidence = 0.0
        previously_confirmed_failure = False
        printer_action = normalize_printer_action(PRINTER_ACTION)
        session_summary = SessionSummary(
            source_name=source.label,
            printer_backend=PRINTER_BACKEND or "simulated",
            printer_action=printer_action,
        )
        print_session_start(session_summary)

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                session_summary.record_frame()
                detection = self._detector.detect(frame)
                if detection.failure_detected:
                    fail_frame_count += 1
                    latest_failure_label = detection.label
                    latest_failure_confidence = detection.confidence
                    session_summary.record_detection()
                else:
                    fail_frame_count = 0
                    latest_failure_label = None
                    latest_failure_confidence = 0.0

                confirmed_failure = fail_frame_count >= self._consecutive_fail_frames
                if confirmed_failure and not previously_confirmed_failure:
                    session_summary.record_confirmed_failure()
                previously_confirmed_failure = confirmed_failure

                now_seconds = monotonic()
                annotated = draw_monitoring_overlay(
                    detection.annotated_frame,
                    OverlayState(
                        source_name=source.label,
                        confirmed_failure=confirmed_failure,
                        fail_frame_count=fail_frame_count,
                        fail_frame_threshold=self._consecutive_fail_frames,
                        label=latest_failure_label,
                        confidence=latest_failure_confidence,
                        cooldown_remaining_seconds=(
                            self._alert_cooldown.remaining_seconds(now_seconds)
                        ),
                        printer_backend=session_summary.printer_backend,
                        printer_action=session_summary.printer_action,
                        last_action_result=session_summary.last_action_result,
                    ),
                )

                if self._should_trigger_actions(
                    confirmed_failure=confirmed_failure,
                    label=latest_failure_label,
                    now_seconds=now_seconds,
                ):
                    self._alert_cooldown.mark_triggered(now_seconds)
                    event = self._trigger_failure_actions(
                        frame=annotated,
                        source=source.label,
                        label=latest_failure_label,
                        confidence=latest_failure_confidence,
                    )
                    if event is not None:
                        result = (
                            "success"
                            if event.action_success
                            else "failed"
                            if event.action_success is False
                            else "unknown"
                        )
                        session_summary.record_action(
                            screenshot_saved=True,
                            action_result=f"{event.action}: {result}",
                        )

                cv2 = _cv2()
                cv2.imshow(WINDOW_NAME, annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            capture.release()
            _cv2().destroyAllWindows()
            session_summary.finish()
            summary_path = None
            try:
                summary_path = session_summary.write_json()
            except OSError as exc:
                print(
                    f"PRINTSENTINEL WARNING: session summary was not saved: {exc}",
                    file=sys.stderr,
                )
            print_session_summary(session_summary, summary_path)

        return None

    def _should_trigger_actions(
        self,
        confirmed_failure: bool,
        label: str | None,
        now_seconds: float,
    ) -> bool:
        """Return whether confirmed failure side effects should run."""

        return (
            confirmed_failure
            and label is not None
            and self._alert_cooldown.is_ready(now_seconds)
        )

    def _trigger_failure_actions(
        self,
        frame: Any,
        source: str,
        label: str,
        confidence: float,
    ) -> Any | None:
        """Trigger Phase 2 failure side effects without crashing monitoring."""

        try:
            return handle_confirmed_failure(frame, source, label, confidence)
        except (OSError, RuntimeError) as exc:
            print(
                f"PRINTSENTINEL WARNING: failure action skipped: {exc}",
                file=sys.stderr,
            )
            return None


def _cv2() -> Any:
    """Import OpenCV only when the monitoring window is active."""

    import cv2

    return cv2
