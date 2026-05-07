"""Read-only WebSocket inspection for Creality-style printer web UIs."""

from __future__ import annotations

import json
import socket
import sys
from dataclasses import dataclass, field
from time import monotonic
from types import ModuleType
from typing import Any
from urllib.parse import urlparse


DEFAULT_PORT = 9999
DEFAULT_CONNECT_TIMEOUT_SECONDS = 2.0
DEFAULT_LISTEN_SECONDS = 5.0
RECV_TIMEOUT_SECONDS = 0.5
PREVIEW_LIMIT_CHARS = 300
MAX_BINARY_PREVIEW_BYTES = 80


@dataclass(frozen=True)
class WebSocketMessageSummary:
    """Summary of one server-sent WebSocket message."""

    index: int
    message_type: str
    json_keys: list[str] = field(default_factory=list)
    preview: str = ""
    truncated: bool = False
    size_bytes: int = 0


@dataclass(frozen=True)
class WebSocketInspectionResult:
    """Read-only WebSocket inspection result."""

    url: str
    connected: bool
    messages: list[WebSocketMessageSummary]
    close_reason: str | None = None

    @property
    def message_count(self) -> int:
        """Return the number of messages received."""

        return len(self.messages)


def build_websocket_url(host: str, port: int = DEFAULT_PORT) -> str:
    """Build a WebSocket URL for a host or IP."""

    normalized_host = normalize_host(host)
    return f"ws://{normalized_host}:{port}"


def normalize_host(host: str) -> str:
    """Return a host without scheme, path, port, or trailing slash."""

    stripped = host.strip()
    parsed = urlparse(stripped if "://" in stripped else f"//{stripped}")
    return (parsed.hostname or parsed.netloc or parsed.path).rstrip("/")


def summarize_message(
    message: str | bytes,
    index: int = 1,
    preview_limit: int = PREVIEW_LIMIT_CHARS,
) -> WebSocketMessageSummary:
    """Summarize a server-sent WebSocket message safely."""

    if isinstance(message, bytes):
        return _summarize_binary_message(message, index, preview_limit)

    text = str(message)
    size_bytes = len(text.encode("utf-8", errors="replace"))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return WebSocketMessageSummary(
            index=index,
            message_type="plain text",
            preview=truncate_text(text, preview_limit)[0],
            truncated=truncate_text(text, preview_limit)[1],
            size_bytes=size_bytes,
        )

    if isinstance(parsed, dict):
        message_type = "JSON object"
        json_keys = sorted(str(key) for key in parsed.keys())
    elif isinstance(parsed, list):
        message_type = "JSON array"
        json_keys = []
    else:
        message_type = "unknown"
        json_keys = []

    preview, truncated = truncate_text(text, preview_limit)
    return WebSocketMessageSummary(
        index=index,
        message_type=message_type,
        json_keys=json_keys,
        preview=preview,
        truncated=truncated,
        size_bytes=size_bytes,
    )


def inspect_websocket(
    host: str,
    port: int = DEFAULT_PORT,
    listen_seconds: float = DEFAULT_LISTEN_SECONDS,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
) -> WebSocketInspectionResult:
    """Connect to a WebSocket and listen briefly for server-sent messages only."""

    url = build_websocket_url(host, port)
    try:
        websocket_module = _load_websocket_module()
    except ImportError as exc:
        return WebSocketInspectionResult(
            url=url,
            connected=False,
            messages=[],
            close_reason=f"websocket-client is not installed: {exc}",
        )

    ws: Any | None = None
    messages: list[WebSocketMessageSummary] = []
    close_reason: str | None = None
    try:
        ws = websocket_module.create_connection(url, timeout=connect_timeout)
        deadline = monotonic() + max(0.0, listen_seconds)
        while monotonic() < deadline:
            remaining_seconds = max(0.0, deadline - monotonic())
            _set_timeout(ws, min(RECV_TIMEOUT_SECONDS, remaining_seconds))
            try:
                message = ws.recv()
            except Exception as exc:
                if _is_timeout_exception(exc, websocket_module):
                    continue
                close_reason = f"receive error: {exc}"
                break

            messages.append(summarize_message(message, index=len(messages) + 1))

        if close_reason is None:
            close_reason = "listen window ended"

        return WebSocketInspectionResult(
            url=url,
            connected=True,
            messages=messages,
            close_reason=close_reason,
        )
    except Exception as exc:
        return WebSocketInspectionResult(
            url=url,
            connected=False,
            messages=[],
            close_reason=f"connection error: {exc}",
        )
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


def print_report(result: WebSocketInspectionResult) -> None:
    """Print a clear read-only WebSocket inspection report."""

    print("PrintSentinel Printer WebSocket Inspection")
    print(f"WebSocket URL: {result.url}")
    print(f"Connected: {'yes' if result.connected else 'no'}")
    print(f"Messages received: {result.message_count}")
    print(f"Close/error reason: {result.close_reason or '-'}")
    print()
    print("Messages:")
    if not result.messages:
        print("  - none")
        return

    for message in result.messages:
        keys = ", ".join(message.json_keys) if message.json_keys else "-"
        truncated = " yes" if message.truncated else " no"
        print(f"  - #{message.index}")
        print(f"    type: {message.message_type}")
        print(f"    size bytes: {message.size_bytes}")
        print(f"    JSON top-level keys: {keys}")
        print(f"    truncated: {truncated}")
        print(f"    preview: {message.preview}")


def main(argv: list[str] | None = None) -> int:
    """Run read-only printer WebSocket inspection from command-line arguments."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or not args[0].strip():
        print(
            "Usage: python tools/inspect_printer_websocket.py <host-or-ip>",
            file=sys.stderr,
        )
        return 2

    result = inspect_websocket(args[0])
    print_report(result)
    return 0 if result.connected else 1


def truncate_text(text: str, limit: int) -> tuple[str, bool]:
    """Return a safely truncated text preview."""

    if len(text) <= limit:
        return text, False
    return f"{text[:limit]}...", True


def _summarize_binary_message(
    message: bytes,
    index: int,
    preview_limit: int,
) -> WebSocketMessageSummary:
    """Summarize binary data without attempting to execute or decode commands."""

    preview_bytes = message[:MAX_BINARY_PREVIEW_BYTES]
    preview = " ".join(f"{byte:02x}" for byte in preview_bytes)
    preview, text_truncated = truncate_text(preview, preview_limit)
    return WebSocketMessageSummary(
        index=index,
        message_type="binary",
        preview=preview,
        truncated=text_truncated or len(message) > len(preview_bytes),
        size_bytes=len(message),
    )


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
    """Import websocket-client lazily so the main app does not depend on it."""

    import websocket

    return websocket


if __name__ == "__main__":
    raise SystemExit(main())
