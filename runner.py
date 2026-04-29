"""OpenCV monitoring loop for PrintSentinel Phase 1."""

from typing import Any

import cv2

from config import (
    COLOR_STATUS_DETAIL,
    COLOR_STATUS_FAIL,
    COLOR_STATUS_OK,
    COLOR_STATUS_TEXT,
    CONSECUTIVE_FAIL_FRAMES,
    STATUS_BAR_HEIGHT,
    STATUS_DETAIL_ORIGIN,
    STATUS_FAIL_DETECTED,
    STATUS_MONITORING,
    STATUS_TEXT_ORIGIN,
    WINDOW_NAME,
)
from detector import YoloFailureDetector
from sources import VideoSource, open_capture


class PrintSentinelRunner:
    """Run detection against a selected video source."""

    def __init__(
        self,
        detector: YoloFailureDetector,
        consecutive_fail_frames: int = CONSECUTIVE_FAIL_FRAMES,
    ) -> None:
        """Create a runner with a detector and confirmation threshold."""

        self._detector = detector
        self._consecutive_fail_frames = consecutive_fail_frames

    def run(self, source: VideoSource) -> str | None:
        """Run the monitoring loop and return an error message if startup fails."""

        capture, error = open_capture(source)
        if error is not None or capture is None:
            return error

        fail_frame_count = 0
        latest_failure_label: str | None = None
        latest_failure_confidence = 0.0

        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                detection = self._detector.detect(frame)
                if detection.failure_detected:
                    fail_frame_count += 1
                    latest_failure_label = detection.label
                    latest_failure_confidence = detection.confidence
                else:
                    fail_frame_count = 0
                    latest_failure_label = None
                    latest_failure_confidence = 0.0

                confirmed_failure = fail_frame_count >= self._consecutive_fail_frames
                annotated = self._draw_status(
                    frame=detection.annotated_frame,
                    confirmed_failure=confirmed_failure,
                    label=latest_failure_label,
                    confidence=latest_failure_confidence,
                )

                cv2.imshow(WINDOW_NAME, annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            capture.release()
            cv2.destroyAllWindows()

        return None

    def _draw_status(
        self,
        frame: Any,
        confirmed_failure: bool,
        label: str | None,
        confidence: float,
    ) -> Any:
        """Draw the top status bar on an annotated frame."""

        status_text = STATUS_FAIL_DETECTED if confirmed_failure else STATUS_MONITORING
        bar_color = COLOR_STATUS_FAIL if confirmed_failure else COLOR_STATUS_OK

        cv2.rectangle(
            frame,
            (0, 0),
            (frame.shape[1], STATUS_BAR_HEIGHT),
            bar_color,
            thickness=-1,
        )
        cv2.putText(
            frame,
            status_text,
            STATUS_TEXT_ORIGIN,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            COLOR_STATUS_TEXT,
            2,
            cv2.LINE_AA,
        )

        if confirmed_failure and label is not None:
            detail = f"{label} ({confidence:.2f})"
            cv2.putText(
                frame,
                detail,
                STATUS_DETAIL_ORIGIN,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                COLOR_STATUS_DETAIL,
                1,
                cv2.LINE_AA,
            )

        return frame
