"""Tests for the read-only Creality WebSocket status client."""

from typing import Any

from creality_status import fetch_creality_status, parse_creality_status_message


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
        """Return messages, then end the receive loop."""

        if self._messages:
            return self._messages.pop(0)
        raise RuntimeError("server closed")

    def send(self, message: Any) -> None:
        """Fail if application-level commands are sent."""

        self.sent_messages.append(message)
        raise AssertionError("status client must not send commands")

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


def test_parse_status_converts_numeric_temperature_strings() -> None:
    """Creality numeric strings should become floats."""

    status = parse_creality_status_message(
        '{"nozzleTemp": "25.050000", "bedTemp0": "31.500000"}'
    )

    assert status.connected
    assert status.nozzle_temp == 25.05
    assert status.bed_temp == 31.5


def test_parse_status_target_temperatures() -> None:
    """Target temperatures should be parsed from Creality keys."""

    status = parse_creality_status_message(
        '{"targetNozzleTemp": "210", "targetBedTemp0": 60}'
    )

    assert status.target_nozzle_temp == 210.0
    assert status.target_bed_temp == 60.0


def test_parse_status_print_file_progress_and_time() -> None:
    """Print details should map to stable status fields."""

    status = parse_creality_status_message(
        (
            '{"printFileName": "benchy.gcode", "printProgress": "42.5", '
            '"printLeftTime": "1234"}'
        )
    )

    assert status.print_file_name == "benchy.gcode"
    assert status.print_progress == 42.5
    assert status.print_left_time == 1234


def test_parse_status_uses_dprogress_fallback() -> None:
    """dProgress should be used when printProgress is absent."""

    status = parse_creality_status_message('{"dProgress": "12.75"}')

    assert status.print_progress == 12.75


def test_parse_status_light_switch_to_bool() -> None:
    """lightSw should be converted to a bool when possible."""

    assert parse_creality_status_message('{"lightSw": "1"}').light_on is True
    assert parse_creality_status_message('{"lightSw": "0"}').light_on is False


def test_parse_status_handles_missing_fields() -> None:
    """Missing fields should remain None without errors."""

    status = parse_creality_status_message('{"hostname": "k1c"}')

    assert status.hostname == "k1c"
    assert status.model is None
    assert status.nozzle_temp is None
    assert status.error is None
    assert status.raw_keys == ("hostname",)


def test_parse_status_handles_malformed_json_safely() -> None:
    """Malformed JSON should produce an error status instead of raising."""

    status = parse_creality_status_message("{bad json")

    assert status.connected
    assert status.error is not None
    assert "malformed JSON" in status.error


def test_fetch_status_handles_connection_failure(monkeypatch) -> None:
    """Connection failures should return a disconnected status."""

    fake_module = FakeWebSocketModule(error=TimeoutError("connect timed out"))
    monkeypatch.setattr(
        "creality_status._load_websocket_module",
        lambda: fake_module,
    )

    status = fetch_creality_status("ws://printer:9999", timeout_seconds=0.25)

    assert not status.connected
    assert status.error == "connection error: connect timed out"


def test_fetch_status_receives_without_sending_commands(monkeypatch) -> None:
    """Fetching status should listen only and close the connection."""

    websocket = FakeWebSocket(
        [
            '{"state": "idle"}',
            (
                '{"hostname": "k1c", "model": "K1C", "state": "printing", '
                '"deviceState": "1", "nozzleTemp": "205.5", '
                '"targetNozzleTemp": "210", "bedTemp0": "60.1", '
                '"targetBedTemp0": "60", "boxTemp": "30", '
                '"printFileName": "part.gcode", "printProgress": "10.5", '
                '"printLeftTime": "321", "lightSw": 1}'
            ),
        ]
    )
    fake_module = FakeWebSocketModule(websocket)
    monkeypatch.setattr(
        "creality_status._load_websocket_module",
        lambda: fake_module,
    )

    status = fetch_creality_status("ws://printer:9999", timeout_seconds=0.25)

    assert status.connected
    assert status.hostname == "k1c"
    assert status.model == "K1C"
    assert status.state == "printing"
    assert status.device_state == "1"
    assert status.nozzle_temp == 205.5
    assert status.target_nozzle_temp == 210.0
    assert status.bed_temp == 60.1
    assert status.target_bed_temp == 60.0
    assert status.box_temp == 30.0
    assert status.print_file_name == "part.gcode"
    assert status.print_progress == 10.5
    assert status.print_left_time == 321
    assert status.light_on is True
    assert websocket.sent_messages == []
    assert websocket.closed
    assert fake_module.create_calls == [("ws://printer:9999", 0.25)]
