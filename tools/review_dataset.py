"""CLI for reviewing captured PrintSentinel dataset metadata."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dataset_review import review_dataset  # noqa: E402


def main() -> int:
    """Print a concise offline dataset review report."""

    summary = review_dataset()
    print("PrintSentinel Dataset Review")
    print(f"Metadata file: {summary['metadata_path']}")
    print(f"Metadata exists: {'yes' if summary['metadata_exists'] else 'no'}")
    print(f"Total captures: {summary['total_captures']}")
    print(f"Malformed JSONL lines skipped: {summary['malformed_lines']}")
    print()

    print("Counts by category:")
    _print_counts(summary["counts_by_category"])
    print()

    print("Counts by source type:")
    _print_counts(summary["counts_by_source_type"])
    print()

    print("Labels seen:")
    _print_counts(summary["labels_seen"])
    print()

    confidence = summary["confidence"]
    if confidence["count"]:
        print(
            "Confidence: "
            f"count={confidence['count']} "
            f"min={confidence['min']:.3f} "
            f"max={confidence['max']:.3f} "
            f"avg={confidence['average']:.3f}"
        )
    else:
        print("Confidence: no numeric confidence values found")

    print(f"Missing files: {summary['missing_files_count']}")
    print()

    print("Suggested next steps:")
    for step in _suggest_next_steps(summary):
        print(f"- {step}")

    return 0


def _print_counts(counts: dict[str, int]) -> None:
    """Print a stable count mapping."""

    if not counts:
        print("- none")
        return
    for name, count in counts.items():
        print(f"- {name}: {count}")


def _suggest_next_steps(summary: dict[str, object]) -> list[str]:
    """Return practical review guidance based on available captures."""

    total_captures = int(summary["total_captures"])
    missing_files_count = int(summary["missing_files_count"])
    if total_captures == 0:
        return [
            "Capture examples from the dashboard using demo video, local video, webcam, or printer camera sources.",
            "Collect a mix of false_positive, true_failure, normal, and unsure samples before exporting.",
            "Run python tools/export_dataset.py when captures are available for annotation prep.",
        ]

    steps = [
        "Review category balance and capture more examples for sparse categories.",
        "Inspect false_positive and unsure samples first; they usually reveal threshold and ROI tuning opportunities.",
        "Run python tools/export_dataset.py to prepare a clean folder for future annotation or fine-tuning work.",
    ]
    if missing_files_count:
        steps.insert(0, "Resolve or recapture rows with missing frame/crop files before relying on the export.")
    return steps


if __name__ == "__main__":
    raise SystemExit(main())
