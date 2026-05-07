"""Tests for session summary serialization."""

from creality_status import CrealityPrinterStatus
from session_summary import SessionSummary


def test_session_summary_records_latest_printer_status() -> None:
    """Latest read-only printer status should be included in summaries."""

    summary = SessionSummary(
        source_name="Printer camera",
        printer_backend="simulated",
        printer_action="stop",
    )

    summary.record_printer_status(
        CrealityPrinterStatus(
            connected=True,
            hostname="K1C-CREALITY1",
            model="K1C",
            nozzle_temp=25.11,
            bed_temp=23.19,
            light_on=True,
        )
    )

    data = summary.to_dict()

    assert data["latest_printer_status"] == {
        "connected": True,
        "hostname": "K1C-CREALITY1",
        "model": "K1C",
        "state": None,
        "device_state": None,
        "nozzle_temp": 25.11,
        "target_nozzle_temp": None,
        "bed_temp": 23.19,
        "target_bed_temp": None,
        "box_temp": None,
        "print_file_name": None,
        "print_progress": None,
        "print_left_time": None,
        "light_on": True,
        "error": None,
    }
