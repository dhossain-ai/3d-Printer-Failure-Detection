"""Printer-control backends for PrintSentinel."""

import json
import sys
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin

import requests

from config import (
    PRINTER_BACKEND,
    PRINTER_API_TOKEN,
    PRINTER_AUTH_HEADER_NAME,
    PRINTER_BASE_URL,
    PRINTER_EXTRA_HEADERS_JSON,
    PRINTER_HEALTH_ENDPOINT,
    PRINTER_PAUSE_ENDPOINT,
    PRINTER_REQUEST_TIMEOUT_SECONDS,
    PRINTER_STOP_ENDPOINT,
    CREALITY_WS_URL,
    CREALITY_CONTROL_TIMEOUT_SECONDS,
)
from creality_control import CrealityWebSocketControlClient
from creality_status import fetch_creality_status


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
        headers: dict[str, str] | None = None,
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
        self._headers = headers or build_request_headers()
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
            response = self._session.get(
                url,
                timeout=self._timeout_seconds,
                headers=self._headers,
            )
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
            response = self._session.post(
                url,
                timeout=self._timeout_seconds,
                headers=self._headers,
            )
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


class CrealityWebSocketPrinterController:
    """Printer controller that uses Creality WebSocket API for safe actions."""

    def __init__(self, ws_url: str, timeout_seconds: float):
        self._ws_url = ws_url
        self._timeout_seconds = timeout_seconds
        self._client = CrealityWebSocketControlClient(ws_url=ws_url, timeout_seconds=timeout_seconds)

    def stop_print(self) -> PrinterCommandResult:
        """Send a real stop command to the Creality printer."""
        res = self._client.stop_print()
        return PrinterCommandResult(action="stop", success=res.success, message=res.message)

    def pause_print(self) -> PrinterCommandResult:
        """Send a real pause command to the Creality printer."""
        res = self._client.pause_print()
        return PrinterCommandResult(action="pause", success=res.success, message=res.message)

    def resume_print(self) -> PrinterCommandResult:
        """Return failure for resume since it is explicitly not confirmed or supported."""
        return PrinterCommandResult(
            action="resume", 
            success=False, 
            message="Resume is not implemented because command is not confirmed."
        )

    def healthcheck(self) -> PrinterCommandResult:
        """Check if WebSocket status endpoint responds."""
        status = fetch_creality_status(self._ws_url, timeout_seconds=self._timeout_seconds)
        if status:
            return PrinterCommandResult(action="healthcheck", success=True, message="Creality WS connected")
        return PrinterCommandResult(action="healthcheck", success=False, message="Creality WS fetch failed")


def create_printer_controller(
    backend: str = PRINTER_BACKEND,
    base_url: str = PRINTER_BASE_URL,
    stop_endpoint: str = PRINTER_STOP_ENDPOINT,
    pause_endpoint: str = PRINTER_PAUSE_ENDPOINT,
    health_endpoint: str = PRINTER_HEALTH_ENDPOINT,
    timeout_seconds: float = PRINTER_REQUEST_TIMEOUT_SECONDS,
    headers: dict[str, str] | None = None,
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
                headers=headers,
            )
        except ValueError as exc:
            print(
                f"PRINTSENTINEL WARNING: {exc} Falling back to simulated backend.",
                file=sys.stderr,
            )
            return SimulatedPrinterController()

    if normalized_backend == "creality_ws":
        ws_url = CREALITY_WS_URL.strip()
        if not ws_url:
            print(
                "PRINTSENTINEL WARNING: creality_ws backend requires CREALITY_WS_URL. Falling back to simulated backend.",
                file=sys.stderr,
            )
            return SimulatedPrinterController()
        return CrealityWebSocketPrinterController(
            ws_url=ws_url, 
            timeout_seconds=CREALITY_CONTROL_TIMEOUT_SECONDS
        )

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


def build_request_headers(
    api_token: str = PRINTER_API_TOKEN,
    auth_header_name: str = PRINTER_AUTH_HEADER_NAME,
    extra_headers_json: str = PRINTER_EXTRA_HEADERS_JSON,
) -> dict[str, str]:
    """Build optional HTTP headers from simple configuration values."""

    headers: dict[str, str] = {}

    if api_token.strip() and auth_header_name.strip():
        headers[auth_header_name.strip()] = api_token.strip()

    if extra_headers_json.strip():
        try:
            extra_headers = json.loads(extra_headers_json)
        except json.JSONDecodeError as exc:
            print(
                f"PRINTSENTINEL WARNING: invalid PRINTER_EXTRA_HEADERS_JSON: {exc}",
                file=sys.stderr,
            )
            extra_headers = {}

        if isinstance(extra_headers, dict):
            headers.update(
                {
                    str(key): str(value)
                    for key, value in extra_headers.items()
                    if str(key).strip()
                }
            )
        else:
            print(
                "PRINTSENTINEL WARNING: PRINTER_EXTRA_HEADERS_JSON must be an object.",
                file=sys.stderr,
            )

    return headers


import time
import csv
from pathlib import Path
from config import LOGS_DIR, PRINTER_BACKEND

def log_printer_command(backend: str, action: str, success: bool, message: str, response_preview: str | None = None):
    try:
        log_file = LOGS_DIR / "printer_commands.csv"
        file_exists = log_file.exists()
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "backend", "action", "success", "message", "response_preview"])
            writer.writerow([
                time.time(),
                backend,
                action,
                success,
                message,
                response_preview or ""
            ])
    except Exception:
        pass


def execute_printer_action(
    controller: PrinterController,
    action: str,
) -> PrinterCommandResult:
    """Run a normalized printer action through a controller."""

    normalized_action = normalize_printer_action(action)
    if normalized_action == "pause":
        res = controller.pause_print()
    else:
        res = controller.stop_print()
        
    response_preview = None
    if hasattr(res, "response_preview"):
        response_preview = res.response_preview
        
    log_printer_command(
        backend=PRINTER_BACKEND, 
        action=res.action, 
        success=res.success, 
        message=res.message,
        response_preview=response_preview
    )
    return res
