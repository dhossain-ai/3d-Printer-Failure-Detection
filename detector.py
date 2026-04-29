"""YOLO-based print failure detection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ultralytics import YOLO

from config import CONFIDENCE_THRESHOLD, FAILURE_CLASSES, MODEL_PATH


@dataclass(frozen=True)
class FrameDetection:
    """Detection output for a single frame."""

    annotated_frame: Any
    failure_detected: bool
    label: str | None
    confidence: float


class YoloFailureDetector:
    """Detect Phase 1 print failure classes with a YOLO model."""

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        failure_classes: tuple[str, ...] = FAILURE_CLASSES,
    ) -> None:
        """Load the YOLO model and configure failure filtering."""

        if not model_path.exists():
            raise FileNotFoundError(f"YOLO model not found: {model_path}")

        self._model = YOLO(str(model_path))
        self._confidence_threshold = confidence_threshold
        self._failure_classes = tuple(label.lower() for label in failure_classes)

    def detect(self, frame: Any) -> FrameDetection:
        """Run detection on one frame and return the annotated result."""

        results = self._model.predict(
            frame,
            conf=self._confidence_threshold,
            verbose=False,
        )
        result = results[0]
        annotated_frame = result.plot() if result is not None else frame.copy()

        label, confidence = self._highest_confidence_failure(result)
        return FrameDetection(
            annotated_frame=annotated_frame,
            failure_detected=label is not None,
            label=label,
            confidence=confidence,
        )

    def _highest_confidence_failure(self, result: Any) -> tuple[str | None, float]:
        """Return the highest-confidence configured failure label."""

        if result.boxes is None:
            return None, 0.0

        names = result.names
        best_label: str | None = None
        best_confidence = 0.0

        for box in result.boxes:
            confidence = float(box.conf[0])
            if confidence < self._confidence_threshold:
                continue

            class_id = int(box.cls[0])
            label = str(names[class_id]).lower()
            if self._is_failure_label(label) and confidence > best_confidence:
                best_label = label
                best_confidence = confidence

        return best_label, best_confidence

    def _is_failure_label(self, label: str) -> bool:
        """Return whether a model label matches a configured failure class."""

        return any(failure_class in label for failure_class in self._failure_classes)
