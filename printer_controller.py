"""Printer-control backends for PrintSentinel."""

import sys
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

import requests

from config import (
    PRINTER_BACKEND,
    PRINTER_BASE_URL,
    PRINTER_HEALTH_ENDPOINT,
    PRINTER_PAUSE_ENDPOINT,
    PRINTER_REQUEST_TIMEOUT_SECONDS,
    PRINTER_STOP_ENDPOINT,
)


@dataclass(frozen=True)
class PrinterCommandResult:
    """Result of a printer-control command."""

    action: str
    success: bool
    message: str


class PrinterController(Protocol):
    """Interface for printer-control backends."""

    def stop_print(self) -> PrinterCommandResult:
        """Request a print stop action."""

    def pause_print(self) -> PrinterCommandResult:
        """Request a print pause action."""

    def healthcheck(self) -> PrinterCommandResult:
        """Check whether the printer-control backend is reachable."""


class SimulatedPrinterController:
    """Printer controller that only prints clear local messages."""

    def stop_print(self) -> PrinterCommandResult:
        """Simulate a printer stop action."""

        message = "SIMULATED PRINTER ACTION: STOP requested."
        print(message, file=sys.stderr)
        return PrinterCommandResult(action="stop", success=True, message=message)

    def pause_print(self) -> PrinterCommandResult:
        """Simulate a printer pause action."""

        message = "SIMULATED PRINTER ACTION: PAUSE requested."
        print(message, file=sys.stderr)
        return PrinterCommandResult(action="pause", success=True, message=message)

    def healthcheck(self) -> PrinterCommandResult:
        """Report simulated backend health."""

        return PrinterCommandResult(
            action="healthcheck",
            success=True,
            message="Simulated printer backend is ready.",
        )


class HttpPrinterController:
    """Printer controller that sends generic HTTP requests to configured endpoints."""

    def __init__(
        self,
        base_url: str,
        stop_endpoint: str = PRINTER_STOP_ENDPOINT,
        pause_endpoint: str = PRINTER_PAUSE_ENDPOINT,
        health_endpoint: str = PRINTER_HEALTH_ENDPOINT,
        timeout_seconds: float = PRINTER_REQUEST_TIMEOUT_SECONDS,
        session: requests.Session | None = None,
    ) -> None:
        """Create an HTTP printer controller."""

        if not base_url.strip():
            raise ValueError("HTTP printer backend requires PRINTER_BASE_URL.")

        self._base_url = base_url.rstrip("/") + "/"
        self._stop_endpoint = stop_endpoint
        self._pause_endpoint = pause_endpoint
        self._health_endpoint = health_endpoint
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def stop_print(self) -> PrinterCommandResult:
        """Send the configured HTTP stop request."""

        return self._post("stop", self._stop_endpoint)

    def pause_print(self) -> PrinterCommandResult:
        """Send the configured HTTP pause request."""

        return self._post("pause", self._pause_endpoint)

    def healthcheck(self) -> PrinterCommandResult:
        """Send the configured HTTP healthcheck request."""

        url = self._build_url(self._health_endpoint)
        try:
            response = self._session.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            return PrinterCommandResult(
                action="healthcheck",
                success=False,
                message=f"HTTP printer healthcheck failed: {exc}",
            )

        return PrinterCommandResult(
            action="healthcheck",
            success=True,
            message=f"HTTP printer healthcheck succeeded: {url}",
        )

    def _post(self, action: str, endpoint: str) -> PrinterCommandResult:
        """Send a POST request for a printer action."""

        url = self._build_url(endpoint)
        try:
            response = self._session.post(url, timeout=self._timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            return PrinterCommandResult(
                action=action,
                success=False,
                message=f"HTTP printer {action} request failed: {exc}",
            )

        return PrinterCommandResult(
            action=action,
            success=True,
            message=f"HTTP printer {action} request succeeded: {url}",
        )

    def _build_url(self, endpoint: str) -> str:
        """Build an absolute endpoint URL from the configured base URL."""

        return urljoin(self._base_url, endpoint.lstrip("/"))


def create_printer_controller(
    backend: str = PRINTER_BACKEND,
    base_url: str = PRINTER_BASE_URL,
    stop_endpoint: str = PRINTER_STOP_ENDPOINT,
    pause_endpoint: str = PRINTER_PAUSE_ENDPOINT,
    health_endpoint: str = PRINTER_HEALTH_ENDPOINT,
    timeout_seconds: float = PRINTER_REQUEST_TIMEOUT_SECONDS,
) -> PrinterController:
    """Create the configured printer controller with safe simulated fallback."""

    normalized_backend = backend.lower().strip()
    if normalized_backend == "http":
        try:
            return HttpPrinterController(
                base_url=base_url,
                stop_endpoint=stop_endpoint,
                pause_endpoint=pause_endpoint,
                health_endpoint=health_endpoint,
                timeout_seconds=timeout_seconds,
            )
        except ValueError as exc:
            print(
                f"PRINTSENTINEL WARNING: {exc} Falling back to simulated backend.",
                file=sys.stderr,
            )
            return SimulatedPrinterController()

    if normalized_backend != "simulated":
        print(
            (
                "PRINTSENTINEL WARNING: unsupported PRINTER_BACKEND "
                f"'{backend}'. Falling back to simulated backend."
            ),
            file=sys.stderr,
        )

    return SimulatedPrinterController()


def normalize_printer_action(action: str) -> str:
    """Return a supported printer action name."""

    if action.lower().strip() == "pause":
        return "pause"

    return "stop"


def execute_printer_action(
    controller: PrinterController,
    action: str,
) -> PrinterCommandResult:
    """Run a normalized printer action through a controller."""

    normalized_action = normalize_printer_action(action)
    if normalized_action == "pause":
        return controller.pause_print()

    return controller.stop_print()
