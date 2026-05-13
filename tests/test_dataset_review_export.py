"""Tests for dataset review and export utilities."""

from __future__ import annotations

import json
from pathlib import Path

from dataset_capture import DATASET_CATEGORIES
from dataset_export import export_dataset
from dataset_review import review_dataset


def test_review_handles_missing_metadata_file(tmp_path: Path) -> None:
    """Missing metadata should produce an empty, successful summary."""

    summary = review_dataset(dataset_dir=tmp_path)

    assert summary["metadata_exists"] is False
    assert summary["total_captures"] == 0
    assert summary["malformed_lines"] == 0
    assert summary["missing_files_count"] == 0
    assert summary["counts_by_category"] == {
        category: 0 for category in DATASET_CATEGORIES
    }


def test_review_counts_categories_correctly(tmp_path: Path) -> None:
    """Review should count captures by category and source type."""

    frame_a = _write_image_placeholder(tmp_path / "raw" / "normal" / "a.jpg")
    frame_b = _write_image_placeholder(
        tmp_path / "raw" / "true_failure" / "b.jpg"
    )
    _write_metadata(
        tmp_path,
        [
            {
                "category": "normal",
                "source_type": "demo_video",
                "label": "ok",
                "confidence": 0.2,
                "frame_path": frame_a.as_posix(),
            },
            {
                "category": "true_failure",
                "source_type": "webcam",
                "label": "spaghetti",
                "confidence": 0.9,
                "frame_path": frame_b.as_posix(),
            },
        ],
    )

    summary = review_dataset(dataset_dir=tmp_path)

    assert summary["total_captures"] == 2
    assert summary["counts_by_category"]["normal"] == 1
    assert summary["counts_by_category"]["true_failure"] == 1
    assert summary["counts_by_source_type"] == {"demo_video": 1, "webcam": 1}
    assert summary["labels_seen"] == {"ok": 1, "spaghetti": 1}
    assert summary["confidence"]["min"] == 0.2
    assert summary["confidence"]["max"] == 0.9
    assert summary["confidence"]["average"] == 0.55


def test_review_skips_malformed_jsonl_safely(tmp_path: Path) -> None:
    """Malformed lines should be counted and skipped without failing review."""

    frame = _write_image_placeholder(tmp_path / "raw" / "normal" / "a.jpg")
    metadata_path = tmp_path / "metadata" / "captures.jsonl"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "category": "normal",
                        "source_type": "demo_video",
                        "frame_path": frame.as_posix(),
                    }
                ),
                "{not-json",
                json.dumps(["not", "a", "dict"]),
            ]
        ),
        encoding="utf-8",
    )

    summary = review_dataset(dataset_dir=tmp_path)

    assert summary["total_captures"] == 1
    assert summary["malformed_lines"] == 2
    assert summary["counts_by_category"]["normal"] == 1


def test_review_reports_missing_image_files(tmp_path: Path) -> None:
    """Review should report missing raw frame and crop file references."""

    _write_metadata(
        tmp_path,
        [
            {
                "category": "false_positive",
                "source_type": "demo_video",
                "frame_path": "raw/false_positive/missing.jpg",
                "crop_path": "crops/false_positive/missing_crop.jpg",
            }
        ],
    )

    summary = review_dataset(dataset_dir=tmp_path)

    assert summary["missing_files_count"] == 2
    assert {missing["field"] for missing in summary["missing_files"]} == {
        "frame_path",
        "crop_path",
    }


def test_export_creates_expected_folder_structure(tmp_path: Path) -> None:
    """Export should create image category folders and metadata folder."""

    output_dir = tmp_path / "exports" / "manual"

    summary = export_dataset(output_dir=output_dir, dataset_dir=tmp_path)

    assert summary["export_dir"] == output_dir.as_posix()
    for category in DATASET_CATEGORIES:
        assert (output_dir / "images" / category).is_dir()
    assert (output_dir / "metadata").is_dir()
    assert (output_dir / "metadata" / "captures.jsonl").exists()
    assert (output_dir / "metadata" / "summary.json").exists()


def test_export_copies_image_files(tmp_path: Path) -> None:
    """Export should copy available raw frame images into category folders."""

    frame = _write_image_placeholder(tmp_path / "raw" / "normal" / "a.jpg")
    _write_metadata(
        tmp_path,
        [
            {
                "category": "normal",
                "source_type": "demo_video",
                "frame_path": frame.as_posix(),
            }
        ],
    )
    output_dir = tmp_path / "exports" / "manual"

    summary = export_dataset(output_dir=output_dir, dataset_dir=tmp_path)

    copied_frame = output_dir / "images" / "normal" / "a.jpg"
    assert copied_frame.read_bytes() == frame.read_bytes()
    assert summary["copied_images_count"] == 1
    assert summary["skipped_images_count"] == 0


def test_export_writes_summary_json(tmp_path: Path) -> None:
    """Export should write review data and export copy stats to summary.json."""

    frame = _write_image_placeholder(tmp_path / "raw" / "normal" / "a.jpg")
    _write_metadata(
        tmp_path,
        [
            {
                "category": "normal",
                "source_type": "demo_video",
                "label": "clean",
                "confidence": 0.12,
                "frame_path": frame.as_posix(),
            }
        ],
    )
    output_dir = tmp_path / "exports" / "manual"

    export_dataset(output_dir=output_dir, dataset_dir=tmp_path)

    summary = json.loads(
        (output_dir / "metadata" / "summary.json").read_text(encoding="utf-8")
    )
    assert summary["total_captures"] == 1
    assert summary["counts_by_category"]["normal"] == 1
    assert summary["copied_images_count"] == 1
    assert summary["labels_seen"] == {"clean": 1}


def test_export_handles_missing_files_gracefully(tmp_path: Path) -> None:
    """Missing source frames should be skipped while export still completes."""

    frame = _write_image_placeholder(tmp_path / "raw" / "normal" / "a.jpg")
    _write_metadata(
        tmp_path,
        [
            {
                "category": "normal",
                "source_type": "demo_video",
                "frame_path": frame.as_posix(),
            },
            {
                "category": "true_failure",
                "source_type": "demo_video",
                "frame_path": "raw/true_failure/missing.jpg",
            },
        ],
    )
    output_dir = tmp_path / "exports" / "manual"

    summary = export_dataset(output_dir=output_dir, dataset_dir=tmp_path)

    assert summary["copied_images_count"] == 1
    assert summary["skipped_images_count"] == 1
    assert summary["missing_files_count"] == 1
    assert (output_dir / "images" / "normal" / "a.jpg").exists()
    assert not (output_dir / "images" / "true_failure" / "missing.jpg").exists()


def _write_metadata(dataset_dir: Path, records: list[dict[str, object]]) -> Path:
    """Write capture metadata JSONL test records."""

    metadata_path = dataset_dir / "metadata" / "captures.jsonl"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        "".join(f"{json.dumps(record)}\n" for record in records),
        encoding="utf-8",
    )
    return metadata_path


def _write_image_placeholder(path: Path) -> Path:
    """Write tiny placeholder bytes for copy-oriented export tests."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-image")
    return path
