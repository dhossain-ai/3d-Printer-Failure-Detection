"""Video source definitions and OpenCV capture helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Union

import requests

from config import PRINTER_CAMERA_TYPE, PRINTER_CAMERA_URL, SAMPLE_VIDEO_PATH

OpenCVSource = Union[int, str]
PRINTER_CAMERA_TYPES = ("stream", "snapshot")
SNAPSHOT_POLL_INTERVAL_SECONDS = 1.0
SNAPSHOT_REQUEST_TIMEOUT_SECONDS = 3.0


class SourceKind(str, Enum):
    """Supported input source types for Phase 1."""

    SAMPLE_VIDEO = "sample_video"
    WEBCAM = "webcam"
    MOBILE_URL = "mobile_url"
    PRINTER_CAMERA = "printer_camera"


@dataclass(frozen=True)
class VideoSource:
    """A user-selected video input source."""

    kind: SourceKind
    label: str
    value: OpenCVSource
    camera_type: str | None = None


def sample_video_source(path: Path = SAMPLE_VIDEO_PATH) -> VideoSource:
    """Return the configured sample video source."""

    return VideoSource(
        kind=SourceKind.SAMPLE_VIDEO,
        label="Sample video",
        value=str(path),
    )


def webcam_source(camera_index: int = 0) -> VideoSource:
    """Return the default webcam source."""

    return VideoSource(
        kind=SourceKind.WEBCAM,
        label=f"Webcam {camera_index}",
        value=camera_index,
    )


def mobile_camera_source(url: str) -> VideoSource:
    """Return a mobile camera stream source."""

    return VideoSource(
        kind=SourceKind.MOBILE_URL,
        label="Mobile camera",
        value=url.strip(),
    )


def printer_camera_source(
    url: str = PRINTER_CAMERA_URL,
    camera_type: str = PRINTER_CAMERA_TYPE,
) -> VideoSource:
    """Return a configured printer camera source."""

    normalized_type = normalize_printer_camera_type(camera_type)
    return VideoSource(
        kind=SourceKind.PRINTER_CAMERA,
        label=f"Printer camera ({normalized_type})",
        value=url.strip(),
        camera_type=normalized_type,
    )


def normalize_printer_camera_type(camera_type: str) -> str:
    """Return a supported printer camera type."""

    normalized_type = camera_type.lower().strip()
    if normalized_type in PRINTER_CAMERA_TYPES:
        return normalized_type
    return "stream"


def validate_source(source: VideoSource) -> str | None:
    """Return an error message when a selected source is not usable."""

    if source.kind == SourceKind.SAMPLE_VIDEO:
        path = Path(str(source.value))
        if not path.exists():
            return f"Sample video not found: {path}"

    if source.kind == SourceKind.MOBILE_URL and not str(source.value).strip():
        return "Mobile camera URL cannot be empty."

    if source.kind == SourceKind.PRINTER_CAMERA and not str(source.value).strip():
        return "Printer camera URL cannot be empty."

    return None


def open_capture(source: VideoSource) -> tuple[Any | None, str | None]:
    """Open a selected source and return a capture or a readable error."""

    validation_error = validate_source(source)
    if validation_error is not None:
        return None, validation_error

    try:
        import cv2
    except ImportError as exc:
        return None, f"OpenCV is not installed or could not be imported: {exc}"

    if source.kind == SourceKind.PRINTER_CAMERA and source.camera_type == "snapshot":
        return PrinterSnapshotCapture(str(source.value)), None

    capture = cv2.VideoCapture(source.value)
    if not capture.isOpened():
        capture.release()
        return None, f"Could not open video source '{source.label}' ({source.value})."

    return capture, None


class PrinterSnapshotCapture:
    """OpenCV-like capture that polls a printer snapshot URL safely."""

    def __init__(
        self,
        url: str,
        timeout_seconds: float = SNAPSHOT_REQUEST_TIMEOUT_SECONDS,
        poll_interval_seconds: float = SNAPSHOT_POLL_INTERVAL_SECONDS,
    ) -> None:
        """Create a snapshot capture for an image URL."""

        self._url = url
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._last_fetch_seconds: float | None = None
        self._released = False

    def read(self) -> tuple[bool, Any | None]:
        """Fetch and decode one snapshot frame."""

        if self._released:
            return False, None

        self._wait_for_poll_interval()
        self._last_fetch_seconds = monotonic()
        response: requests.Response | None = None
        try:
            response = requests.get(self._url, timeout=self._timeout_seconds)
            response.raise_for_status()
            frame = self._decode_image(response.content)
        except requests.RequestException:
            return False, None
        except Exception:
            return False, None
        finally:
            if response is not None:
                response.close()

        if frame is None:
            return False, None

        return True, frame

    def release(self) -> None:
        """Mark the snapshot capture as released."""

        self._released = True

    def isOpened(self) -> bool:  # noqa: N802 - Match OpenCV capture API.
        """Return whether the capture is available for reads."""

        return not self._released and bool(self._url.strip())

    def _wait_for_poll_interval(self) -> None:
        """Avoid polling the printer snapshot endpoint too frequently."""

        if self._last_fetch_seconds is None:
            return

        elapsed_seconds = monotonic() - self._last_fetch_seconds
        wait_seconds = self._poll_interval_seconds - elapsed_seconds
        if wait_seconds > 0:
            sleep(wait_seconds)

    @staticmethod
    def _decode_image(image_bytes: bytes) -> Any | None:
        """Decode image bytes into an OpenCV frame."""

        import cv2
        import numpy as np

        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        if image_array.size == 0:
            return None
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
