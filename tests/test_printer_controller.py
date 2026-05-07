"""Tests for printer controller backends."""

import requests

from printer_controller import (
    HttpPrinterController,
    PrinterCommandResult,
    SimulatedPrinterController,
    CrealityWebSocketPrinterController,
    build_request_headers,
    create_printer_controller,
    execute_printer_action,
    log_printer_command,
)
from unittest.mock import patch, MagicMock
from creality_control import CrealityCommandResult


class FakeResponse:
    """Minimal response object for HTTP controller tests."""

    def __init__(self, error: requests.RequestException | None = None) -> None:
        """Create a fake response that can optionally fail."""

        self._error = error

    def raise_for_status(self) -> None:
        """Raise the configured HTTP error if present."""

        if self._error is not None:
            raise self._error


class FakeSession:
    """Minimal requests-like session for routing tests."""

    def __init__(self, error: requests.RequestException | None = None) -> None:
        """Create a fake session that records requests."""

        self.error = error
        self.get_calls: list[tuple[str, float]] = []
        self.post_calls: list[tuple[str, float]] = []

    def get(
        self,
        url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        """Record a GET request."""

        self.get_calls.append((url, timeout))
        if self.error is not None:
            raise self.error
        return FakeResponse()

    def post(
        self,
        url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        """Record a POST request."""

        self.post_calls.append((url, timeout))
        if self.error is not None:
            raise self.error
        return FakeResponse()


def test_create_printer_controller_defaults_to_simulated() -> None:
    """The default safe backend should be simulated."""

    controller = create_printer_controller(backend="simulated")

    assert isinstance(controller, SimulatedPrinterController)


def test_create_printer_controller_falls_back_when_http_config_missing(capsys) -> None:
    """Missing HTTP base URL should fall back safely."""

    controller = create_printer_controller(backend="http", base_url="")

    assert isinstance(controller, SimulatedPrinterController)
    assert "Falling back to simulated backend" in capsys.readouterr().err


def test_simulated_controller_reports_success(capsys) -> None:
    """Simulated actions should print clear messages and succeed."""

    controller = SimulatedPrinterController()
    result = controller.stop_print()

    assert result == PrinterCommandResult(
        action="stop",
        success=True,
        message="SIMULATED PRINTER ACTION: STOP requested.",
    )
    assert "STOP requested" in capsys.readouterr().err


def test_http_controller_routes_stop_pause_and_health_requests() -> None:
    """HTTP controller should send requests to configured endpoints."""

    session = FakeSession()
    controller = HttpPrinterController(
        base_url="http://printer.local/api",
        stop_endpoint="/job/stop",
        pause_endpoint="/job/pause",
        health_endpoint="/status",
        timeout_seconds=2.5,
        session=session,
    )

    assert controller.healthcheck().success
    assert controller.stop_print().success
    assert controller.pause_print().success

    assert session.get_calls == [("http://printer.local/api/status", 2.5)]
    assert session.post_calls == [
        ("http://printer.local/api/job/stop", 2.5),
        ("http://printer.local/api/job/pause", 2.5),
    ]


def test_http_controller_returns_failure_without_raising() -> None:
    """HTTP request failures should return a failed command result."""

    session = FakeSession(error=requests.Timeout("timeout"))
    controller = HttpPrinterController(
        base_url="http://printer.local",
        timeout_seconds=1.0,
        session=session,
    )

    result = controller.stop_print()

    assert not result.success
    assert result.action == "stop"
    assert "failed" in result.message


def test_execute_printer_action_routes_pause() -> None:
    """Action routing should call the requested controller method."""

    controller = SimulatedPrinterController()

    assert execute_printer_action(controller, "pause").action == "pause"
    assert execute_printer_action(controller, "unknown").action == "stop"


def test_build_request_headers_adds_token_and_extra_headers() -> None:
    """HTTP headers should combine token and JSON extras."""

    headers = build_request_headers(
        api_token="Bearer secret",
        auth_header_name="Authorization",
        extra_headers_json='{"X-Printer": "demo"}',
    )

    assert headers == {
        "Authorization": "Bearer secret",
        "X-Printer": "demo",
    }


def test_build_request_headers_ignores_invalid_json(capsys) -> None:
    """Invalid extra header JSON should warn and continue safely."""

    headers = build_request_headers(
        api_token="secret",
        auth_header_name="X-Api-Key",
        extra_headers_json="{bad json",
    )

    assert headers == {"X-Api-Key": "secret"}
    assert "invalid PRINTER_EXTRA_HEADERS_JSON" in capsys.readouterr().err


@patch("printer_controller.CrealityWebSocketControlClient")
def test_creality_ws_controller_pause_and_stop(mock_client_class):
    mock_instance = MagicMock()
    mock_instance.pause_print.return_value = CrealityCommandResult(action="pause_print", success=True, message="ok")
    mock_instance.stop_print.return_value = CrealityCommandResult(action="stop_print", success=True, message="ok")
    mock_client_class.return_value = mock_instance
    
    controller = CrealityWebSocketPrinterController(ws_url="ws://test", timeout_seconds=5)
    
    assert controller.pause_print().success
    assert controller.stop_print().success
    assert not controller.resume_print().success
    
    mock_instance.pause_print.assert_called_once()
    mock_instance.stop_print.assert_called_once()


@patch("printer_controller.fetch_creality_status")
def test_creality_ws_controller_healthcheck(mock_fetch):
    controller = CrealityWebSocketPrinterController(ws_url="ws://test", timeout_seconds=5)
    
    mock_fetch.return_value = {"model": "K1C"}
    assert controller.healthcheck().success
    
    mock_fetch.return_value = None
    assert not controller.healthcheck().success


def test_create_printer_controller_creality_ws(capsys):
    with patch("printer_controller.CREALITY_WS_URL", "ws://test"):
        controller = create_printer_controller(backend="creality_ws")
        assert isinstance(controller, CrealityWebSocketPrinterController)
    
    # Missing URL fallback
    with patch("printer_controller.CREALITY_WS_URL", ""):
        controller = create_printer_controller(backend="creality_ws")
        assert isinstance(controller, SimulatedPrinterController)
        assert "requires CREALITY_WS_URL" in capsys.readouterr().err


def test_log_printer_command(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "printer_commands.csv"
    
    with patch("printer_controller.LOGS_DIR", log_dir):
        log_printer_command("test_backend", "test_action", True, "test_message")
        
        assert log_file.exists()
        content = log_file.read_text()
        assert "test_backend" in content
        assert "test_action" in content
        assert "test_message" in content
        assert "timestamp" in content # Header exists
