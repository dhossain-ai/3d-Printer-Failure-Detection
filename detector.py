"""YOLO-based print failure detection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import CONFIDENCE_THRESHOLD, FAILURE_CLASSES, MODEL_DEVICE, MODEL_PATH


MODEL_DEVICE_ERROR_HINT = (
    "YOLO prediction failed while initializing model inference. This can happen "
    "when torch and torchvision CUDA builds do not match, including errors around "
    "torchvision::nms, the CUDA backend, or an invalid GPU device id. Set "
    "PRINTSENTINEL_MODEL_DEVICE=cpu to force CPU inference, or install matching "
    "torch and torchvision CUDA builds before using GPU inference."
)


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
        model_device: str = MODEL_DEVICE,
    ) -> None:
        """Load the YOLO model and configure failure filtering."""

        if not model_path.exists():
            raise FileNotFoundError(
                f"YOLO model not found at {model_path}. "
                "Place a trained model at models/model.pt and try again."
            )

        try:
            from ultralytics import YOLO

            self._model = YOLO(str(model_path))
        except Exception as exc:
            raise RuntimeError(f"Could not load YOLO model from {model_path}: {exc}") from exc

        self._confidence_threshold = confidence_threshold
        self._failure_classes = tuple(label.lower() for label in failure_classes)
        self._model_device = normalize_model_device(model_device)

    def detect(self, frame: Any) -> FrameDetection:
        """Run detection on one frame and return the annotated result."""

        try:
            results = self._model.predict(
                frame,
                conf=self._confidence_threshold,
                verbose=False,
                **self._device_predict_kwargs(),
            )
        except Exception as exc:
            if _is_model_device_error(exc):
                raise RuntimeError(
                    f"{MODEL_DEVICE_ERROR_HINT} Original error: {exc}"
                ) from exc
            raise

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

    def _device_predict_kwargs(self) -> dict[str, str]:
        """Return YOLO predict kwargs for the configured model device."""

        if self._model_device == "auto":
            return {}
        return {"device": self._model_device}


def normalize_model_device(model_device: str) -> str:
    """Return a supported model inference device."""

    normalized_device = model_device.lower().strip()
    if normalized_device in {"auto", "cpu", "cuda", "0"}:
        return normalized_device
    return "auto"


def _is_model_device_error(exc: Exception) -> bool:
    """Return whether an exception matches known torch/CUDA device issues."""

    message = str(exc).lower()
    return any(
        error_text in message
        for error_text in (
            "torchvision::nms",
            "cuda backend",
            "invalid device id",
        )
    )
