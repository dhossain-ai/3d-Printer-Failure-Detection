"""Tests for Creality WebSocket control."""

import json
from unittest.mock import MagicMock, patch

import pytest
import websocket

from creality_control import CrealityWebSocketControlClient


@pytest.fixture
def mock_ws():
    with patch("creality_control.websocket.create_connection") as mock_create:
        mock_conn = MagicMock()
        mock_create.return_value = mock_conn
        yield mock_conn


def test_set_light_on(mock_ws):
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_light(True)
    
    assert result.success is True
    assert result.action == "light_on"
    mock_ws.send.assert_called_once_with(json.dumps({"method": "set", "params": {"lightSw": 1}}))


def test_set_light_off(mock_ws):
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_light(False)
    
    assert result.success is True
    assert result.action == "light_off"
    mock_ws.send.assert_called_once_with(json.dumps({"method": "set", "params": {"lightSw": 0}}))


def test_set_model_fan_on(mock_ws):
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_model_fan(True)
    
    assert result.success is True
    assert result.action == "model_fan_on"
    mock_ws.send.assert_called_once_with(json.dumps({"method": "set", "params": {"fan": 1}}))


def test_set_auxiliary_fan_on(mock_ws):
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_auxiliary_fan(True)
    
    assert result.success is True
    assert result.action == "auxiliary_fan_on"
    mock_ws.send.assert_called_once_with(json.dumps({"method": "set", "params": {"fanAuxiliary": 1}}))


def test_set_case_fan_on(mock_ws):
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_case_fan(True)
    
    assert result.success is True
    assert result.action == "case_fan_on"
    mock_ws.send.assert_called_once_with(json.dumps({"method": "set", "params": {"fanCase": 1}}))


def test_request_file_list(mock_ws):
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.request_file_list()
    
    assert result.success is True
    assert result.action == "request_file_list"
    mock_ws.send.assert_called_once_with(json.dumps({"method": "get", "params": {"reqGcodeFile": 1}}))


def test_connection_failure():
    with patch("creality_control.websocket.create_connection", side_effect=Exception("Connection refused")):
        client = CrealityWebSocketControlClient("ws://test:9999")
        result = client.set_light(True)
        
        assert result.success is False
        assert "Connection refused" in result.message


def test_send_failure(mock_ws):
    mock_ws.send.side_effect = Exception("Send failed")
    
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_light(True)
    
    assert result.success is False
    assert "Send failed" in result.message


def test_response_preview_truncated(mock_ws):
    long_response = "A" * 300
    mock_ws.recv.return_value = long_response
    
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_light(True)
    
    assert result.success is True
    assert result.response_preview is not None
    assert len(result.response_preview) == 203  # 200 + '...'
    assert result.response_preview.endswith("...")


def test_response_timeout_is_handled(mock_ws):
    mock_ws.recv.side_effect = websocket.WebSocketTimeoutException("Timeout")
    
    client = CrealityWebSocketControlClient("ws://test:9999")
    result = client.set_light(True)
    
    assert result.success is True
    assert result.response_preview is None


def test_no_arbitrary_send_method():
    client = CrealityWebSocketControlClient("ws://test:9999")
    public_methods = [method for method in dir(client) if callable(getattr(client, method)) and not method.startswith("_")]
    
    allowed_methods = {
        "set_light",
        "set_model_fan",
        "set_auxiliary_fan",
        "set_case_fan",
        "request_file_list"
    }
    
    for method in public_methods:
        assert method in allowed_methods, f"Found unapproved method: {method}"


def test_request_file_list_skips_status_and_finds_target(mock_ws):
    mock_ws.recv.side_effect = [
        json.dumps({"someStatus": 1}),
        json.dumps({"anotherStatus": 2}),
        json.dumps({"retGcodeFileInfo": [{"name": "test.gcode"}]})
    ]
    
    client = CrealityWebSocketControlClient("ws://test:9999", timeout_seconds=1.0)
    result = client.request_file_list()
    
    assert result.success is True
    assert result.response_preview is not None
    assert "retGcodeFileInfo" in result.response_preview
    assert mock_ws.recv.call_count == 3


def test_request_file_list_timeout_after_status(mock_ws):
    import time
    def slow_recv():
        time.sleep(0.6)
        return json.dumps({"someStatus": 1})
        
    mock_ws.recv.side_effect = slow_recv
    
    client = CrealityWebSocketControlClient("ws://test:9999", timeout_seconds=1.0)
    result = client.request_file_list()
    
    assert result.success is True
    assert "response was not observed" in result.message
    assert result.response_preview is None


def test_request_file_list_malformed_json(mock_ws):
    mock_ws.recv.side_effect = [
        "not-json",
        json.dumps({"retGcodeFileInfo": []})
    ]
    
    client = CrealityWebSocketControlClient("ws://test:9999", timeout_seconds=1.0)
    result = client.request_file_list()
    
    assert result.success is True
    assert result.response_preview is not None
    assert "retGcodeFileInfo" in result.response_preview
    assert mock_ws.recv.call_count == 2
