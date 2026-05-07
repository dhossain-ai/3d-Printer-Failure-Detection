"""Tests for background Creality status polling."""

from creality_status import CrealityPrinterStatus
from creality_status_poller import CrealityStatusPoller


def test_status_poller_stores_latest_successful_status() -> None:
    """A successful poll should update the latest in-memory status."""

    status = CrealityPrinterStatus(
        connected=True,
        hostname="K1C-CREALITY1",
        model="K1C",
    )
    calls: list[tuple[str, float]] = []

    def fake_fetcher(ws_url: str, timeout_seconds: float) -> CrealityPrinterStatus:
        calls.append((ws_url, timeout_seconds))
        return status

    poller = CrealityStatusPoller(
        ws_url="ws://printer:9999",
        poll_seconds=5,
        timeout_seconds=2,
        fetcher=fake_fetcher,
    )

    poller.poll_once()

    assert poller.latest_status == status
    assert calls == [("ws://printer:9999", 2)]


def test_status_poller_handles_fetch_error_safely(capsys) -> None:
    """Fetcher errors should not escape monitoring."""

    def fake_fetcher(ws_url: str, timeout_seconds: float) -> CrealityPrinterStatus:
        raise RuntimeError("status unavailable")

    poller = CrealityStatusPoller(
        ws_url="ws://printer:9999",
        poll_seconds=5,
        timeout_seconds=2,
        fetcher=fake_fetcher,
    )

    poller.poll_once()

    assert poller.latest_status is None
    assert "Creality status poll failed" in capsys.readouterr().err
