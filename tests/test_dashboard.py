"""Tests for local web dashboard."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import config
from web_dashboard.app import app
from creality_control import CrealityCommandResult


client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_config():
    """Reset relevant config variables before each test."""
    original_ws_url = config.CREALITY_WS_URL
    original_control_enabled = config.CREALITY_CONTROL_ENABLED
    
    yield
    
    config.CREALITY_WS_URL = original_ws_url
    config.CREALITY_CONTROL_ENABLED = original_control_enabled


def test_dashboard_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "PrintSentinel" in response.text


def test_api_config_no_secrets():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "control_enabled" in data
    assert "camera_configured" in data
    assert "status_ws_configured" in data
    assert "model_device" in data
    # Ensure no tokens or passwords
    assert "TELEGRAM_BOT_TOKEN" not in data
    assert "SMTP_PASSWORD" not in data
    assert "PRINTER_API_TOKEN" not in data


def test_api_status_missing_ws_url():
    config.CREALITY_WS_URL = ""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert "not configured" in data["error"].lower()


@patch("web_dashboard.app.fetch_creality_status")
def test_api_status_success(mock_fetch):
    config.CREALITY_WS_URL = "ws://test"
    mock_fetch.return_value = {"model": "K1C"}
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["status"]["model"] == "K1C"


def test_control_light_rejected_when_disabled():
    config.CREALITY_CONTROL_ENABLED = False
    response = client.post("/api/control/light", json={"enabled": True})
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


def test_control_fan_rejected_when_disabled():
    config.CREALITY_CONTROL_ENABLED = False
    response = client.post("/api/control/fan", json={"fan": "model", "percent": 50})
    assert response.status_code == 403


@patch("web_dashboard.app.CrealityWebSocketControlClient")
def test_control_light_calls_client(mock_client_class):
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    
    mock_instance = MagicMock()
    mock_instance.set_light.return_value = CrealityCommandResult(action="light_on", success=True, message="ok")
    mock_client_class.return_value = mock_instance
    
    response = client.post("/api/control/light", json={"enabled": True})
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    mock_instance.set_light.assert_called_once_with(True)


@patch("web_dashboard.app.CrealityWebSocketControlClient")
def test_control_fan_calls_client(mock_client_class):
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    
    mock_instance = MagicMock()
    mock_instance.set_model_fan_percent.return_value = CrealityCommandResult(action="model_fan_50pct", success=True, message="ok")
    mock_client_class.return_value = mock_instance
    
    response = client.post("/api/control/fan", json={"fan": "model", "percent": 50})
    assert response.status_code == 200
    
    mock_instance.set_model_fan_percent.assert_called_once_with(50)


def test_control_fan_rejects_invalid_fan_name():
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    response = client.post("/api/control/fan", json={"fan": "invalid_fan", "percent": 50})
    assert response.status_code == 400
    assert "unknown fan type" in response.json()["detail"].lower()


def test_control_fan_rejects_invalid_percent():
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    response = client.post("/api/control/fan", json={"fan": "model", "percent": 150})
    assert response.status_code == 400
    assert "between 0 and 100" in response.json()["detail"].lower()


def test_no_arbitrary_or_unsafe_endpoints():
    routes = [route.path for route in app.routes]
    
    unsafe_keywords = ["pause", "stop", "cancel", "temp", "move", "home", "extrude"]
    
    for route in routes:
        for keyword in unsafe_keywords:
            assert keyword not in route.lower(), f"Unsafe endpoint found: {route}"


def test_recent_events_missing_file(tmp_path):
    with patch("web_dashboard.app.config.EVENTS_CSV_PATH", tmp_path / "does_not_exist.csv"):
        response = client.get("/api/events/recent")
        assert response.status_code == 200
        assert response.json() == {"events": []}


def test_recent_events_newest_first(tmp_path):
    events_file = tmp_path / "events.csv"
    events_file.write_text("timestamp,label\n1,A\n2,B\n3,C", encoding="utf-8")
    
    with patch("web_dashboard.app.config.EVENTS_CSV_PATH", events_file):
        response = client.get("/api/events/recent")
        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) == 3
        assert events[0]["timestamp"] == "3"
        assert events[1]["timestamp"] == "2"
        assert events[2]["timestamp"] == "1"


def test_recent_events_malformed_csv(tmp_path):
    events_file = tmp_path / "events.csv"
    events_file.write_text("timestamp,label\n1,A\nmalformed\n3,C", encoding="utf-8")
    
    with patch("web_dashboard.app.config.EVENTS_CSV_PATH", events_file):
        response = client.get("/api/events/recent")
        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) == 3
        # The reader handles malformed row by putting rest in None key or similar, but it doesn't crash


def test_recent_notifications_missing_file(tmp_path):
    with patch("web_dashboard.app.config.LOGS_DIR", tmp_path):
        response = client.get("/api/notifications/recent")
        assert response.status_code == 200
        assert response.json() == {"notifications": []}


@patch("web_dashboard.app.CrealityWebSocketControlClient")
def test_files_api_parses_retGcodeFileInfo(mock_client_class):
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    
    import json
    mock_instance = MagicMock()
    mock_instance.request_file_list.return_value = CrealityCommandResult(
        action="request_file_list", 
        success=True, 
        message="ok",
        response_preview=json.dumps({"retGcodeFileInfo": [{"name": "test1.gcode"}, {"name": "test2.gcode"}]})
    )
    mock_client_class.return_value = mock_instance
    
    response = client.get("/api/files")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["files"]) == 2
    assert data["files"][0]["name"] == "test1.gcode"
    assert data["files"][1]["name"] == "test2.gcode"
