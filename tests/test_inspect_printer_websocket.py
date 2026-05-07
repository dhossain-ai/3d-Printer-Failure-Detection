"""Tests for the read-only printer WebSocket inspector."""

from typing import Any

from tools.inspect_printer_websocket import (
    build_websocket_url,
    inspect_websocket,
    main,
    summarize_message,
)


class FakeTimeout(Exception):
    """Fake websocket timeout exception."""


class FakeWebSocket:
    """Fake websocket-client connection."""

    def __init__(self, messages: list[str | bytes]) -> None:
        """Create a fake connection with messages to receive."""

        self._messages = messages
        self.closed = False
        self.sent_messages: list[Any] = []
        self.timeouts: list[float] = []

    def recv(self) -> str | bytes:
        """Return messages, then close the receive loop."""

        if self._messages:
            return self._messages.pop(0)
        raise RuntimeError("server closed")

    def send(self, message: Any) -> None:
        """Fail if application-level commands are sent."""

        self.sent_messages.append(message)
        raise AssertionError("inspector must not send application-level commands")

    def settimeout(self, timeout: float) -> None:
        """Record receive timeouts."""

        self.timeouts.append(timeout)

    def close(self) -> None:
        """Record close."""

        self.closed = True


class FakeWebSocketModule:
    """Fake websocket-client module."""

    WebSocketTimeoutException = FakeTimeout

    def __init__(
        self,
        websocket: FakeWebSocket | None = None,
        error: Exception | None = None,
    ) -> None:
        """Create a fake module with optional connection failure."""

        self.websocket = websocket or FakeWebSocket([])
        self.error = error
        self.create_calls: list[tuple[str, float]] = []

    def create_connection(self, url: str, timeout: float) -> FakeWebSocket:
        """Record connection requests."""

        self.create_calls.append((url, timeout))
        if self.error is not None:
            raise self.error
        return self.websocket


def test_builds_default_websocket_url_from_host() -> None:
    """The inspector should target ws://host:9999."""

    assert build_websocket_url("192.168.137.211") == "ws://192.168.137.211:9999"
    assert (
        build_websocket_url("http://192.168.137.211/")
        == "ws://192.168.137.211:9999"
    )


def test_summarizes_json_object_message() -> None:
    """JSON object messages should include top-level keys."""

    summary = summarize_message('{"status": "ready", "temp": 25}', index=3)

    assert summary.index == 3
    assert summary.message_type == "JSON object"
    assert summary.json_keys == ["status", "temp"]
    assert summary.preview == '{"status": "ready", "temp": 25}'


def test_summarizes_json_array_message() -> None:
    """JSON arrays should be classified separately."""

    summary = summarize_message('[{"status": "ready"}]')

    assert summary.message_type == "JSON array"
    assert summary.json_keys == []


def test_summarizes_plain_text_message() -> None:
    """Plain text should remain readable."""

    summary = summarize_message("printer ready")

    assert summary.message_type == "plain text"
    assert summary.preview == "printer ready"


def test_summarizes_binary_message_safely() -> None:
    """Binary messages should be shown as a hex preview."""

    summary = summarize_message(b"\x00\x01\xfe\xff")

    assert summary.message_type == "binary"
    assert summary.preview == "00 01 fe ff"
    assert summary.size_bytes == 4


def test_truncates_long_messages() -> None:
    """Long previews should be truncated."""

    summary = summarize_message("x" * 20, preview_limit=5)

    assert summary.preview == "xxxxx..."
    assert summary.truncated


def test_inspect_websocket_receives_messages_without_sending(monkeypatch) -> None:
    """Inspection should connect, receive server messages, close, and never send."""

    websocket = FakeWebSocket(['{"state": "idle"}', "hello"])
    fake_module = FakeWebSocketModule(websocket)
    monkeypatch.setattr(
        "tools.inspect_printer_websocket._load_websocket_module",
        lambda: fake_module,
    )

    result = inspect_websocket(
        "192.168.137.211",
        listen_seconds=5,
        connect_timeout=0.25,
    )

    assert result.url == "ws://192.168.137.211:9999"
    assert result.connected
    assert result.message_count == 2
    assert [message.message_type for message in result.messages] == [
        "JSON object",
        "plain text",
    ]
    assert fake_module.create_calls == [("ws://192.168.137.211:9999", 0.25)]
    assert websocket.sent_messages == []
    assert websocket.closed


def test_inspect_websocket_handles_connection_failure(monkeypatch) -> None:
    """Connection errors should produce a failed inspection result."""

    fake_module = FakeWebSocketModule(error=TimeoutError("connect timed out"))
    monkeypatch.setattr(
        "tools.inspect_printer_websocket._load_websocket_module",
        lambda: fake_module,
    )

    result = inspect_websocket("192.168.137.211", connect_timeout=0.25)

    assert not result.connected
    assert result.message_count == 0
    assert result.close_reason == "connection error: connect timed out"


def test_main_returns_nonzero_without_host(capsys) -> None:
    """The CLI should require an explicit host or IP."""

    assert main([]) != 0
    assert "Usage:" in capsys.readouterr().err
