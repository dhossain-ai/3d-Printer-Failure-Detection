"""CLI for reading Creality printer status from a WebSocket feed."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import CREALITY_STATUS_TIMEOUT_SECONDS  # noqa: E402
from creality_status import CrealityPrinterStatus, fetch_creality_status  # noqa: E402


def print_status(status: CrealityPrinterStatus) -> None:
    """Print a concise read-only Creality status report."""

    print("PrintSentinel Creality WebSocket Status")
    print(f"Connected: {'yes' if status.connected else 'no'}")
    print(f"Hostname: {_format_value(status.hostname)}")
    print(f"Model: {_format_value(status.model)}")
    print(f"State: {_format_value(status.state)}")
    print(f"Device state: {_format_value(status.device_state)}")
    print(
        "Nozzle temp: "
        f"{_format_value(status.nozzle_temp)} / "
        f"{_format_value(status.target_nozzle_temp)}"
    )
    print(
        "Bed temp: "
        f"{_format_value(status.bed_temp)} / "
        f"{_format_value(status.target_bed_temp)}"
    )
    print(f"Box temp: {_format_value(status.box_temp)}")
    print(f"Print file: {_format_value(status.print_file_name)}")
    print(f"Progress: {_format_value(status.print_progress)}")
    print(f"Time left: {_format_value(status.print_left_time)}")
    print(f"Light on: {_format_value(status.light_on)}")
    print(f"Raw keys: {', '.join(status.raw_keys) if status.raw_keys else '-'}")
    print(f"Error: {_format_value(status.error)}")


def main(argv: list[str] | None = None) -> int:
    """Read Creality status from a configured WebSocket URL."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or not args[0].strip():
        print(
            "Usage: python tools/read_creality_status.py <ws-url>",
            file=sys.stderr,
        )
        return 2

    status = fetch_creality_status(
        ws_url=args[0],
        timeout_seconds=CREALITY_STATUS_TIMEOUT_SECONDS,
    )
    print_status(status)
    return 0 if status.connected and status.error is None else 1


def _format_value(value: object) -> str:
    """Format optional status values for terminal output."""

    if value is None:
        return "-"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
