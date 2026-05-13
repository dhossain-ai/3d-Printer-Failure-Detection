"""Dataset capture helpers for dashboard-driven model improvement."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from utils import now_local, safe_filename_part, safe_timestamp

DATASET_CATEGORIES = ("false_positive", "true_failure", "normal", "unsure")
DATASET_DIR = config.BASE_DIR / "dataset"
METADATA_PATH = DATASET_DIR / "metadata" / "captures.jsonl"


@dataclass(frozen=True)
class DatasetFrameSnapshot:
    """Frame and detection state captured from dashboard monitoring."""

    raw_frame: Any | None
    annotated_frame: Any | None
    bounding_box: tuple[int, int, int, int] | None
    source_type: str
    source_name: str
    source_value: str
    label: str | None
    confidence: float
    confirmed_failure: bool
    model_device: str = config.MODEL_DEVICE


def capture_dataset_frame(
    snapshot: DatasetFrameSnapshot,
    category: str,
    notes: str = "",
    dataset_dir: Path | None = None,
) -> dict[str, Any]:
    """Save the latest dashboard frame and append dataset metadata."""

    normalized_category = normalize_dataset_category(category)
    if snapshot.raw_frame is None:
        raise ValueError("No frame is available to capture yet.")

    root_dir = dataset_dir or DATASET_DIR
    timestamp = now_local()
    capture_id = _build_capture_id(timestamp, normalized_category, snapshot.label)
    raw_path = root_dir / "raw" / normalized_category / f"{capture_id}.jpg"
    annotated_path = (
        root_dir / "raw" / normalized_category / f"{capture_id}_annotated.jpg"
    )
    crop_path = root_dir / "crops" / normalized_category / f"{capture_id}_crop.jpg"
    metadata_path = root_dir / "metadata" / "captures.jsonl"

    _ensure_dataset_dirs(root_dir)
    _write_image(raw_path, snapshot.raw_frame)

    saved_annotated_path: Path | None = None
    if snapshot.annotated_frame is not None:
        _write_image(annotated_path, snapshot.annotated_frame)
        saved_annotated_path = annotated_path

    saved_crop_path = _try_write_crop(
        crop_path=crop_path,
        frame=snapshot.raw_frame,
        bounding_box=snapshot.bounding_box,
    )

    metadata = {
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "category": normalized_category,
        "source_type": snapshot.source_type,
        "source_name": snapshot.source_name,
        "source_value": snapshot.source_value,
        "label": snapshot.label,
        "confidence": snapshot.confidence,
        "confirmed_failure": snapshot.confirmed_failure,
        "frame_path": raw_path.as_posix(),
        "annotated_frame_path": (
            saved_annotated_path.as_posix() if saved_annotated_path else None
        ),
        "crop_path": saved_crop_path.as_posix() if saved_crop_path else None,
        "model_device": snapshot.model_device,
        "notes": notes.strip(),
    }
    _append_metadata(metadata_path, metadata)
    return metadata


def normalize_dataset_category(category: str) -> str:
    """Return a supported dataset category or raise a validation error."""

    normalized = category.strip().lower()
    if normalized not in DATASET_CATEGORIES:
        raise ValueError(
            "Category must be false_positive, true_failure, normal, or unsure."
        )
    return normalized


def _ensure_dataset_dirs(dataset_dir: Path) -> None:
    """Create generated dataset folders on demand."""

    for category in DATASET_CATEGORIES:
        (dataset_dir / "raw" / category).mkdir(parents=True, exist_ok=True)
        (dataset_dir / "crops" / category).mkdir(parents=True, exist_ok=True)
    (dataset_dir / "metadata").mkdir(parents=True, exist_ok=True)


def _write_image(path: Path, frame: Any) -> None:
    """Write an image frame using OpenCV."""

    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Could not save dataset image: {path}")


def _try_write_crop(
    crop_path: Path,
    frame: Any,
    bounding_box: tuple[int, int, int, int] | None,
) -> Path | None:
    """Write a detection crop when a valid bounding box is available."""

    if bounding_box is None:
        return None

    try:
        height, width = frame.shape[:2]
    except Exception:
        return None

    x1, y1, x2, y2 = bounding_box
    x1 = max(0, min(width, x1))
    x2 = max(0, min(width, x2))
    y1 = max(0, min(height, y1))
    y2 = max(0, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame[y1:y2, x1:x2]
    if getattr(crop, "size", 0) == 0:
        return None

    _write_image(crop_path, crop)
    return crop_path


def _append_metadata(metadata_path: Path, metadata: dict[str, Any]) -> None:
    """Append one JSON metadata record to the JSONL file."""

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("a", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, sort_keys=True)
        metadata_file.write("\n")


def _build_capture_id(
    timestamp: datetime,
    category: str,
    label: str | None,
) -> str:
    """Build a filesystem-safe capture identifier."""

    label_part = safe_filename_part(label or "unlabeled")
    return f"{safe_timestamp(timestamp)}_{category}_{label_part}"
