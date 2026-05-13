"""CLI for exporting captured PrintSentinel dataset frames."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dataset_export import export_dataset  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Export captured dataset frames into a categorized folder."""

    parser = argparse.ArgumentParser(
        description="Export PrintSentinel captured dataset frames.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional export directory, for example dataset/exports/manual_export.",
    )
    args = parser.parse_args(argv)

    summary = export_dataset(output_dir=args.output)
    print("PrintSentinel Dataset Export")
    print(f"Export folder: {summary['export_dir']}")
    print(f"Total captures reviewed: {summary['total_captures']}")
    print(f"Images copied: {summary['copied_images_count']}")
    print(f"Images skipped: {summary['skipped_images_count']}")
    print(f"Missing files reported by review: {summary['missing_files_count']}")
    print("Metadata written:")
    print(f"- {Path(summary['export_dir']) / 'metadata' / 'captures.jsonl'}")
    print(f"- {Path(summary['export_dir']) / 'metadata' / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
