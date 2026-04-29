"""Video source definitions and OpenCV capture helpers."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Union

from config import SAMPLE_VIDEO_PATH

OpenCVSource = Union[int, str]


class SourceKind(str, Enum):
    """Supported input source types for Phase 1."""

    SAMPLE_VIDEO = "sample_video"
    WEBCAM = "webcam"
    MOBILE_URL = "mobile_url"


@dataclass(frozen=True)
class VideoSource:
    """A user-selected video input source."""

    kind: SourceKind
    label: str
    value: OpenCVSource


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


def validate_source(source: VideoSource) -> str | None:
    """Return an error message when a selected source is not usable."""

    if source.kind == SourceKind.SAMPLE_VIDEO:
        path = Path(str(source.value))
        if not path.exists():
            return f"Sample video not found: {path}"

    if source.kind == SourceKind.MOBILE_URL and not str(source.value).strip():
        return "Mobile camera URL cannot be empty."

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

    capture = cv2.VideoCapture(source.value)
    if not capture.isOpened():
        capture.release()
        return None, f"Could not open video source '{source.label}' ({source.value})."

    return capture, None
