"""Export captured dataset frames into a clean folder for annotation."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from dataset_capture import DATASET_CATEGORIES, DATASET_DIR, METADATA_PATH
from dataset_review import review_dataset
from utils import safe_timestamp


def export_dataset(
    output_dir: Path | None = None,
    dataset_dir: Path | None = None,
    metadata_path: Path | None = None,
) -> dict[str, Any]:
    """Create a categorized image export without modifying source captures."""

    root_dir = dataset_dir or DATASET_DIR
    captures_path = metadata_path or root_dir / "metadata" / "captures.jsonl"
    if metadata_path is None and dataset_dir is None:
        captures_path = METADATA_PATH

    export_dir = output_dir or root_dir / "exports" / safe_timestamp(datetime.now())
    images_dir = export_dir / "images"
    metadata_dir = export_dir / "metadata"

    for category in DATASET_CATEGORIES:
        (images_dir / category).mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    summary = review_dataset(metadata_path=captures_path, dataset_dir=root_dir)
    copied_images: list[dict[str, Any]] = []
    skipped_images: list[dict[str, Any]] = []

    if captures_path.exists():
        shutil.copy2(captures_path, metadata_dir / "captures.jsonl")
        for line_number, capture in _iter_capture_records(captures_path):
            category = str(capture.get("category") or "unsure")
            if category not in DATASET_CATEGORIES:
                category = "unsure"

            frame_path_value = capture.get("frame_path")
            if not frame_path_value:
                skipped_images.append(
                    {
                        "line_number": line_number,
                        "reason": "missing frame_path metadata",
                    }
                )
                continue

            source_path = _resolve_capture_path(frame_path_value, root_dir)
            if not source_path.exists():
                skipped_images.append(
                    {
                        "line_number": line_number,
                        "reason": "source image not found",
                        "path": str(frame_path_value),
                    }
                )
                continue

            destination_path = _unique_destination_path(
                images_dir / category / source_path.name
            )
            shutil.copy2(source_path, destination_path)
            copied_images.append(
                {
                    "line_number": line_number,
                    "category": category,
                    "source": source_path.as_posix(),
                    "destination": destination_path.as_posix(),
                }
            )
    else:
        (metadata_dir / "captures.jsonl").write_text("", encoding="utf-8")

    export_summary = {
        **summary,
        "export_dir": export_dir.as_posix(),
        "copied_images_count": len(copied_images),
        "skipped_images_count": len(skipped_images),
        "copied_images": copied_images,
        "skipped_images": skipped_images,
    }
    (metadata_dir / "summary.json").write_text(
        json.dumps(export_summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return export_summary


def _iter_capture_records(metadata_path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Read valid capture records while skipping malformed JSONL lines."""

    records: list[tuple[int, dict[str, Any]]] = []
    with metadata_path.open("r", encoding="utf-8") as metadata_file:
        for line_number, line in enumerate(metadata_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue
            try:
                record = json.loads(stripped_line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append((line_number, record))
    return records


def _resolve_capture_path(path_value: object, dataset_dir: Path) -> Path:
    """Resolve capture paths stored as absolute or dataset-relative strings."""

    path = Path(str(path_value))
    if path.is_absolute():
        return path
    return dataset_dir / path


def _unique_destination_path(destination_path: Path) -> Path:
    """Avoid overwriting when multiple metadata rows reference same filename."""

    if not destination_path.exists():
        return destination_path

    stem = destination_path.stem
    suffix = destination_path.suffix
    parent = destination_path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
