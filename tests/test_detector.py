"""Tests for YOLO detector behavior that do not require a real model."""

from types import SimpleNamespace

import pytest

from detector import MODEL_DEVICE_ERROR_HINT, YoloFailureDetector


class FakeResult:
    """Minimal YOLO result stand-in."""

    boxes = None
    names: dict[int, str] = {}

    def plot(self) -> str:
        """Return a fake annotated frame."""

        return "annotated"


class FakeModel:
    """Fake YOLO model that records predict calls."""

    def __init__(self, error: Exception | None = None) -> None:
        """Create a fake model with an optional predict error."""

        self.error = error
        self.predict_calls: list[dict[str, object]] = []

    def predict(self, *args: object, **kwargs: object) -> list[FakeResult]:
        """Record predict kwargs and return one fake result."""

        self.predict_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return [FakeResult()]


class FakeBox:
    """Minimal Ultralytics box stand-in."""

    def __init__(self, confidence: float, class_id: int, xyxy: list[float]) -> None:
        """Create a fake detection box."""

        self.conf = [confidence]
        self.cls = [class_id]
        self.xyxy = [xyxy]


def make_detector(
    model_device: str,
    model: FakeModel | None = None,
) -> YoloFailureDetector:
    """Create a detector without loading Ultralytics."""

    detector = YoloFailureDetector.__new__(YoloFailureDetector)
    detector._model = model or FakeModel()
    detector._confidence_threshold = 0.35
    detector._failure_classes = ("spaghetti",)
    detector._model_device = model_device
    return detector


def test_detector_does_not_pass_device_when_model_device_is_auto() -> None:
    """Auto device mode should leave device selection to Ultralytics."""

    model = FakeModel()
    detector = make_detector("auto", model)

    detector.detect(object())

    assert model.predict_calls == [{"conf": 0.35, "verbose": False}]


@pytest.mark.parametrize("model_device", ["cpu", "cuda", "0"])
def test_detector_passes_configured_model_device(model_device: str) -> None:
    """Explicit model device values should be passed to YOLO predict."""

    model = FakeModel()
    detector = make_detector(model_device, model)

    detector.detect(object())

    assert model.predict_calls == [
        {"conf": 0.35, "verbose": False, "device": model_device}
    ]


@pytest.mark.parametrize(
    "error_message",
    [
        "operator torchvision::nms does not exist",
        "Torch was not compiled with CUDA backend",
        "Invalid device id 0",
    ],
)
def test_detector_adds_helpful_message_for_cuda_and_nms_errors(
    error_message: str,
) -> None:
    """Known torch/CUDA prediction failures should include recovery guidance."""

    detector = make_detector("cuda", FakeModel(RuntimeError(error_message)))

    with pytest.raises(RuntimeError) as exc_info:
        detector.detect(object())

    assert MODEL_DEVICE_ERROR_HINT in str(exc_info.value)
    assert "PRINTSENTINEL_MODEL_DEVICE=cpu" in str(exc_info.value)
    assert error_message in str(exc_info.value)


def test_detector_does_not_swallow_unrelated_prediction_errors() -> None:
    """Unrelated prediction failures should preserve their original exception."""

    original_error = ValueError("unexpected model output")
    detector = make_detector("auto", FakeModel(original_error))

    with pytest.raises(ValueError, match="unexpected model output"):
        detector.detect(object())


def test_detector_returns_best_failure_bounding_box() -> None:
    """Detector output should include the highest-confidence failure box."""

    detector = make_detector("auto")
    result = SimpleNamespace(
        boxes=[
            FakeBox(0.4, 0, [1.2, 2.4, 8.6, 9.1]),
            FakeBox(0.8, 1, [3.0, 4.0, 13.0, 14.0]),
        ],
        names={0: "spaghetti", 1: "normal"},
    )

    label, confidence, bounding_box = detector._highest_confidence_failure(result)

    assert label == "spaghetti"
    assert confidence == pytest.approx(0.4)
    assert bounding_box == (1, 2, 9, 9)
