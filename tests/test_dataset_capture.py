"""Tests for dashboard dataset capture helpers."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from dataset_capture import DatasetFrameSnapshot, capture_dataset_frame


def make_snapshot(
    bounding_box: tuple[int, int, int, int] | None = (2, 2, 8, 8),
) -> DatasetFrameSnapshot:
    """Build a representative dataset frame snapshot."""

    raw_frame = np.zeros((10, 10, 3), dtype="uint8")
    annotated_frame = np.full((10, 10, 3), 80, dtype="uint8")
    return DatasetFrameSnapshot(
        raw_frame=raw_frame,
        annotated_frame=annotated_frame,
        bounding_box=bounding_box,
        source_type="demo_video",
        source_name="Sample video",
        source_value="assets/demo.mp4",
        label="spaghetti",
        confidence=0.91,
        confirmed_failure=True,
        model_device="cpu",
    )


def test_capture_rejects_invalid_category(tmp_path: Path) -> None:
    """Invalid dataset categories should be rejected before writing files."""

    with pytest.raises(ValueError, match="Category must be"):
        capture_dataset_frame(make_snapshot(), "bad", dataset_dir=tmp_path)


def test_capture_rejects_missing_frame(tmp_path: Path) -> None:
    """Capture should fail clearly when no raw frame is available."""

    snapshot = DatasetFrameSnapshot(
        raw_frame=None,
        annotated_frame=None,
        bounding_box=None,
        source_type="webcam",
        source_name="Webcam 0",
        source_value="0",
        label=None,
        confidence=0.0,
        confirmed_failure=False,
    )

    with pytest.raises(ValueError, match="No frame is available"):
        capture_dataset_frame(snapshot, "normal", dataset_dir=tmp_path)


def test_capture_saves_raw_frame_and_metadata_jsonl(tmp_path: Path) -> None:
    """Capture should save frames and append a JSONL metadata record."""

    metadata = capture_dataset_frame(
        make_snapshot(),
        "true_failure",
        notes="real spaghetti",
        dataset_dir=tmp_path,
    )

    frame_path = Path(metadata["frame_path"])
    annotated_path = Path(metadata["annotated_frame_path"])
    crop_path = Path(metadata["crop_path"])
    metadata_path = tmp_path / "metadata" / "captures.jsonl"

    assert frame_path.exists()
    assert annotated_path.exists()
    assert crop_path.exists()
    assert cv2.imread(str(frame_path)) is not None
    assert metadata["category"] == "true_failure"
    assert metadata["notes"] == "real spaghetti"

    records = [
        json.loads(line)
        for line in metadata_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["frame_path"] == metadata["frame_path"]
    assert records[0]["model_device"] == "cpu"


def test_capture_handles_missing_crop_gracefully(tmp_path: Path) -> None:
    """Missing bounding boxes should still save raw and annotated frames."""

    metadata = capture_dataset_frame(
        make_snapshot(bounding_box=None),
        "false_positive",
        dataset_dir=tmp_path,
    )

    assert Path(metadata["frame_path"]).exists()
    assert Path(metadata["annotated_frame_path"]).exists()
    assert metadata["crop_path"] is None
