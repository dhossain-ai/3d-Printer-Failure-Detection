"""Tests for video source construction and capture helpers."""

from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np
import requests

from sources import (
    PrinterSnapshotCapture,
    SourceKind,
    mobile_camera_source,
    open_capture,
    printer_camera_source,
    sample_video_source,
    validate_source,
    webcam_source,
)


class FakeVideoCapture:
    """Small cv2.VideoCapture stand-in."""

    calls: list[str | int] = []

    def __init__(self, value: str | int) -> None:
        """Record the source value."""

        self.value = value
        self.released = False
        self.calls.append(value)

    def isOpened(self) -> bool:  # noqa: N802 - Match OpenCV API.
        """Return that the fake capture opened."""

        return True

    def release(self) -> None:
        """Record release."""

        self.released = True


class FakeResponse:
    """Small response object for snapshot tests."""

    def __init__(
        self,
        content: bytes = b"",
        error: requests.RequestException | None = None,
    ) -> None:
        """Create a fake response."""

        self.content = content
        self.error = error
        self.closed = False

    def raise_for_status(self) -> None:
        """Raise the configured error, if present."""

        if self.error is not None:
            raise self.error

    def close(self) -> None:
        """Record close."""

        self.closed = True


def test_existing_source_builders_still_work(tmp_path) -> None:
    """Existing source constructors should keep their public behavior."""

    sample = sample_video_source(tmp_path / "demo.mp4")
    webcam = webcam_source()
    mobile = mobile_camera_source(" http://phone/video ")

    assert sample.kind == SourceKind.SAMPLE_VIDEO
    assert sample.label == "Sample video"
    assert sample.value == str(tmp_path / "demo.mp4")
    assert webcam.kind == SourceKind.WEBCAM
    assert webcam.value == 0
    assert mobile.kind == SourceKind.MOBILE_URL
    assert mobile.value == "http://phone/video"


def test_printer_stream_mode_builds_video_source_from_configured_url() -> None:
    """Printer stream mode should produce a source that OpenCV can consume."""

    source = printer_camera_source(
        " http://printer:8080/?action=stream ",
        "stream",
    )

    assert source.kind == SourceKind.PRINTER_CAMERA
    assert source.label == "Printer camera (stream)"
    assert source.value == "http://printer:8080/?action=stream"
    assert source.camera_type == "stream"


def test_empty_printer_camera_url_returns_clear_validation_error() -> None:
    """Printer camera selection should have a clear empty URL error path."""

    source = printer_camera_source("", "stream")

    assert validate_source(source) == "Printer camera URL cannot be empty."


def test_open_capture_uses_video_capture_for_printer_stream(monkeypatch) -> None:
    """Printer stream mode should reuse the normal OpenCV capture path."""

    FakeVideoCapture.calls = []
    fake_cv2 = SimpleNamespace(VideoCapture=FakeVideoCapture)
    monkeypatch.setitem(__import__("sys").modules, "cv2", fake_cv2)

    source = printer_camera_source("http://printer:8080/?action=stream", "stream")
    capture, error = open_capture(source)

    assert error is None
    assert isinstance(capture, FakeVideoCapture)
    assert FakeVideoCapture.calls == ["http://printer:8080/?action=stream"]


def test_open_capture_builds_snapshot_capture_for_printer_snapshot() -> None:
    """Printer snapshot mode should build a polling snapshot capture."""

    source = printer_camera_source("http://printer:8080/?action=snapshot", "snapshot")

    capture, error = open_capture(source)

    assert error is None
    assert isinstance(capture, PrinterSnapshotCapture)


def test_snapshot_mode_fetches_image_bytes_and_decodes_frame(monkeypatch) -> None:
    """Snapshot capture should fetch image bytes and decode an OpenCV frame."""

    image = np.zeros((2, 2, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    response = FakeResponse(encoded.tobytes())
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, timeout: float) -> FakeResponse:
        calls.append({"url": url, "timeout": timeout})
        return response

    monkeypatch.setattr("sources.requests.get", fake_get)
    capture = PrinterSnapshotCapture(
        "http://printer:8080/?action=snapshot",
        timeout_seconds=1.5,
        poll_interval_seconds=0,
    )

    read_ok, frame = capture.read()

    assert read_ok
    assert frame is not None
    assert frame.shape == (2, 2, 3)
    assert calls == [
        {
            "url": "http://printer:8080/?action=snapshot",
            "timeout": 1.5,
        }
    ]
    assert response.closed


def test_snapshot_mode_handles_request_timeout_safely(monkeypatch) -> None:
    """Snapshot capture should return a failed read on request failures."""

    def fake_get(url: str, timeout: float) -> FakeResponse:
        raise requests.Timeout("snapshot timed out")

    monkeypatch.setattr("sources.requests.get", fake_get)
    capture = PrinterSnapshotCapture(
        "http://printer:8080/?action=snapshot",
        poll_interval_seconds=0,
    )

    assert capture.read() == (False, None)
