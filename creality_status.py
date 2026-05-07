"""Read-only Creality WebSocket printer status client."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from time import monotonic
from types import ModuleType
from typing import Any

from config import CREALITY_STATUS_TIMEOUT_SECONDS, CREALITY_WS_URL


RECV_TIMEOUT_SECONDS = 0.5


@dataclass(frozen=True)
class CrealityPrinterStatus:
    """Parsed read-only Creality printer status."""

    connected: bool
    hostname: str | None = None
    model: str | None = None
    state: str | None = None
    device_state: str | None = None
    nozzle_temp: float | None = None
    target_nozzle_temp: float | None = None
    bed_temp: float | None = None
    target_bed_temp: float | None = None
    box_temp: float | None = None
    print_file_name: str | None = None
    print_progress: float | None = None
    print_left_time: int | None = None
    light_on: bool | None = None
    raw_keys: tuple[str, ...] = ()
    error: str | None = None


def parse_creality_status_message(message: str | bytes) -> CrealityPrinterStatus:
    """Parse a Creality WebSocket status message safely."""

    try:
        text = (
            message.decode("utf-8", errors="replace")
            if isinstance(message, bytes)
            else message
        )
        payload = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        return CrealityPrinterStatus(
            connected=True,
            error=f"malformed JSON status message: {exc}",
        )

    if not isinstance(payload, dict):
        return CrealityPrinterStatus(
            connected=True,
            error="status message was not a JSON object",
        )

    return CrealityPrinterStatus(
        connected=True,
        hostname=_optional_string(payload.get("hostname")),
        model=_optional_string(payload.get("model")),
        state=_optional_string(payload.get("state")),
        device_state=_optional_string(payload.get("deviceState")),
        nozzle_temp=_optional_float(payload.get("nozzleTemp")),
        target_nozzle_temp=_optional_float(payload.get("targetNozzleTemp")),
        bed_temp=_optional_float(payload.get("bedTemp0")),
        target_bed_temp=_optional_float(payload.get("targetBedTemp0")),
        box_temp=_optional_float(payload.get("boxTemp")),
        print_file_name=_optional_string(payload.get("printFileName")),
        print_progress=_optional_float(
            payload.get("printProgress", payload.get("dProgress"))
        ),
        print_left_time=_optional_int(payload.get("printLeftTime")),
        light_on=_optional_bool(payload.get("lightSw")),
        raw_keys=tuple(sorted(str(key) for key in payload.keys())),
        error=None,
    )


def fetch_creality_status(
    ws_url: str = CREALITY_WS_URL,
    timeout_seconds: float = CREALITY_STATUS_TIMEOUT_SECONDS,
) -> CrealityPrinterStatus:
    """Fetch the richest/latest Creality status message without sending commands."""

    if not ws_url.strip():
        return CrealityPrinterStatus(
            connected=False,
            error="Creality WebSocket URL is not configured.",
        )

    try:
        websocket_module = _load_websocket_module()
    except ImportError as exc:
        return CrealityPrinterStatus(
            connected=False,
            error=f"websocket-client is not installed: {exc}",
        )

    ws: Any | None = None
    best_status: CrealityPrinterStatus | None = None
    latest_error: str | None = None
    try:
        ws = websocket_module.create_connection(ws_url, timeout=timeout_seconds)
        deadline = monotonic() + max(0.0, timeout_seconds)
        while monotonic() < deadline:
            remaining_seconds = max(0.0, deadline - monotonic())
            _set_timeout(ws, min(RECV_TIMEOUT_SECONDS, remaining_seconds))
            try:
                message = ws.recv()
            except Exception as exc:
                if _is_timeout_exception(exc, websocket_module):
                    continue
                latest_error = f"receive error: {exc}"
                break

            status = parse_creality_status_message(message)
            if status.error is not None:
                latest_error = status.error
                continue
            if _is_richer_status(status, best_status):
                best_status = status

        if best_status is not None:
            return best_status

        return CrealityPrinterStatus(
            connected=True,
            error=latest_error or "No valid status message received.",
        )
    except Exception as exc:
        return CrealityPrinterStatus(
            connected=False,
            error=f"connection error: {exc}",
        )
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


def status_richness(status: CrealityPrinterStatus) -> int:
    """Return how many parsed status fields are populated."""

    values = (
        status.hostname,
        status.model,
        status.state,
        status.device_state,
        status.nozzle_temp,
        status.target_nozzle_temp,
        status.bed_temp,
        status.target_bed_temp,
        status.box_temp,
        status.print_file_name,
        status.print_progress,
        status.print_left_time,
        status.light_on,
    )
    return sum(value is not None for value in values)


def _is_richer_status(
    status: CrealityPrinterStatus,
    current: CrealityPrinterStatus | None,
) -> bool:
    """Return whether a status should replace the current best status."""

    if current is None:
        return True
    return status_richness(status) >= status_richness(current)


def _optional_string(value: object) -> str | None:
    """Convert a value to a stripped optional string."""

    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _optional_float(value: object) -> float | None:
    """Convert numeric strings or numbers to float."""

    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    """Convert numeric strings or numbers to int."""

    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    """Convert common Creality boolean-ish values to bool."""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "open"}:
        return True
    if text in {"0", "false", "no", "off", "close", "closed"}:
        return False
    return None


def _set_timeout(ws: Any, timeout_seconds: float) -> None:
    """Set a short receive timeout when the WebSocket object supports it."""

    if hasattr(ws, "settimeout"):
        ws.settimeout(timeout_seconds)


def _is_timeout_exception(exc: Exception, websocket_module: ModuleType) -> bool:
    """Return whether an exception indicates a receive timeout."""

    timeout_types = [socket.timeout, TimeoutError]
    websocket_timeout = getattr(websocket_module, "WebSocketTimeoutException", None)
    if websocket_timeout is not None:
        timeout_types.append(websocket_timeout)
    return isinstance(exc, tuple(timeout_types))


def _load_websocket_module() -> ModuleType:
    """Import websocket-client lazily."""

    import websocket

    return websocket
