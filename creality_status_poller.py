"""Background read-only Creality status polling."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

from creality_status import CrealityPrinterStatus, fetch_creality_status


StatusFetcher = Callable[[str, float], CrealityPrinterStatus]


class CrealityStatusPoller:
    """Poll Creality WebSocket status in a background thread."""

    def __init__(
        self,
        ws_url: str,
        poll_seconds: float,
        timeout_seconds: float,
        fetcher: StatusFetcher = fetch_creality_status,
    ) -> None:
        """Create a read-only status poller."""

        self._ws_url = ws_url
        self._poll_seconds = max(1.0, poll_seconds)
        self._timeout_seconds = max(0.5, timeout_seconds)
        self._fetcher = fetcher
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._latest_status: CrealityPrinterStatus | None = None

    @property
    def latest_status(self) -> CrealityPrinterStatus | None:
        """Return the most recent status snapshot, if any."""

        with self._lock:
            return self._latest_status

    def start(self) -> None:
        """Start background polling."""

        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="CrealityStatusPoller",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling and wait briefly for the thread."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._timeout_seconds + 1.0)

    def poll_once(self) -> None:
        """Fetch one status update without raising into callers."""

        try:
            status = self._fetcher(self._ws_url, self._timeout_seconds)
        except Exception as exc:
            print(
                f"PRINTSENTINEL WARNING: Creality status poll failed: {exc}",
                file=sys.stderr,
            )
            return

        with self._lock:
            self._latest_status = status

    def _run(self) -> None:
        """Run the polling loop."""

        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(self._poll_seconds)
