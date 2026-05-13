"""Review captured dataset metadata for future model improvement."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from dataset_capture import DATASET_CATEGORIES, DATASET_DIR, METADATA_PATH


def review_dataset(
    metadata_path: Path | None = None,
    dataset_dir: Path | None = None,
) -> dict[str, Any]:
    """Return a structured summary of captured dataset metadata."""

    root_dir = dataset_dir or DATASET_DIR
    captures_path = metadata_path or root_dir / "metadata" / "captures.jsonl"
    if metadata_path is None and dataset_dir is None:
        captures_path = METADATA_PATH

    summary: dict[str, Any] = {
        "metadata_path": captures_path.as_posix(),
        "metadata_exists": captures_path.exists(),
        "total_captures": 0,
        "malformed_lines": 0,
        "counts_by_category": {category: 0 for category in DATASET_CATEGORIES},
        "counts_by_source_type": {},
        "labels_seen": {},
        "confidence": {
            "count": 0,
            "min": None,
            "max": None,
            "average": None,
        },
        "missing_files_count": 0,
        "missing_files": [],
    }

    if not captures_path.exists():
        return summary

    confidences: list[float] = []
    category_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    missing_files: list[dict[str, Any]] = []

    with captures_path.open("r", encoding="utf-8") as metadata_file:
        for line_number, line in enumerate(metadata_file, start=1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            try:
                capture = json.loads(stripped_line)
            except json.JSONDecodeError:
                summary["malformed_lines"] += 1
                continue

            if not isinstance(capture, dict):
                summary["malformed_lines"] += 1
                continue

            summary["total_captures"] += 1
            category = str(capture.get("category") or "unknown")
            source_type = str(capture.get("source_type") or "unknown")
            label = capture.get("label") or "unlabeled"

            category_counts[category] += 1
            source_type_counts[source_type] += 1
            label_counts[str(label)] += 1

            confidence = _coerce_confidence(capture.get("confidence"))
            if confidence is not None:
                confidences.append(confidence)

            for field_name in ("frame_path", "crop_path"):
                raw_path = capture.get(field_name)
                if not raw_path:
                    continue
                resolved_path = _resolve_capture_path(raw_path, root_dir)
                if not resolved_path.exists():
                    missing_files.append(
                        {
                            "line_number": line_number,
                            "field": field_name,
                            "path": str(raw_path),
                        }
                    )

    summary["counts_by_category"].update(dict(sorted(category_counts.items())))
    summary["counts_by_source_type"] = dict(sorted(source_type_counts.items()))
    summary["labels_seen"] = dict(sorted(label_counts.items()))
    summary["missing_files"] = missing_files
    summary["missing_files_count"] = len(missing_files)

    if confidences:
        summary["confidence"] = {
            "count": len(confidences),
            "min": min(confidences),
            "max": max(confidences),
            "average": sum(confidences) / len(confidences),
        }

    return summary


def _coerce_confidence(value: object) -> float | None:
    """Return a numeric confidence value when metadata contains one."""

    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_capture_path(path_value: object, dataset_dir: Path) -> Path:
    """Resolve capture paths stored as absolute or dataset-relative strings."""

    path = Path(str(path_value))
    if path.is_absolute():
        return path
    return dataset_dir / path
