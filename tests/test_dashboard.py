"""Tests for local web dashboard."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

import config
import notifications.settings as notification_settings
from notifications.models import NotificationResult
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
    
    unsafe_keywords = ["cancel", "temp", "move", "home", "extrude"]
    
    # Pause and stop are now explicitly allowed as safe whitelisted control endpoints
    allowed_whitelisted_endpoints = ["/api/control/pause", "/api/control/stop"]
    
    for route in routes:
        if route in allowed_whitelisted_endpoints:
            continue
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


@patch("web_dashboard.app.CrealityWebSocketControlClient")
def test_dashboard_pause_print(mock_client_class):
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    
    mock_instance = MagicMock()
    mock_instance.pause_print.return_value = CrealityCommandResult(action="pause_print", success=True, message="ok")
    mock_client_class.return_value = mock_instance
    
    response = client.post("/api/control/pause")
    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_instance.pause_print.assert_called_once()


def test_dashboard_pause_print_disabled():
    config.CREALITY_CONTROL_ENABLED = False
    response = client.post("/api/control/pause")
    assert response.status_code == 403


@patch("web_dashboard.app.CrealityWebSocketControlClient")
def test_dashboard_stop_print(mock_client_class):
    config.CREALITY_CONTROL_ENABLED = True
    config.CREALITY_WS_URL = "ws://test"
    
    mock_instance = MagicMock()
    mock_instance.stop_print.return_value = CrealityCommandResult(action="stop_print", success=True, message="ok")
    mock_client_class.return_value = mock_instance
    
    # Missing confirmation
    response = client.post("/api/control/stop", json={"confirm": "NO"})
    assert response.status_code == 400
    
    # Correct confirmation
    response = client.post("/api/control/stop", json={"confirm": "STOP"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_instance.stop_print.assert_called_once()


def _load_settings_from(path: Path):
    return notification_settings.load_notification_settings(path=path)


def _save_settings_to(settings, path: Path):
    return notification_settings.save_notification_settings(settings, path=path)


def test_get_notification_settings_masks_secrets(tmp_path: Path):
    settings_path = tmp_path / "config" / "local_notification_settings.json"
    notification_settings.save_notification_settings(
        {
            "NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_BOT_TOKEN": "123456:SECRET",
            "TELEGRAM_CHAT_ID": "987654321",
            "EMAIL_NOTIFICATIONS_ENABLED": True,
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": 465,
            "SMTP_SECURITY": "ssl",
            "SMTP_USERNAME": "printer@example.com",
            "SMTP_PASSWORD": "email-secret",
            "EMAIL_FROM": "printer@example.com",
            "EMAIL_TO": "ops@example.com",
        },
        path=settings_path,
    )

    with (
        patch("web_dashboard.app.LOCAL_NOTIFICATION_SETTINGS_PATH", settings_path),
        patch("web_dashboard.app.load_notification_settings", side_effect=lambda: _load_settings_from(settings_path)),
    ):
        response = client.get("/api/settings/notifications")

    assert response.status_code == 200
    data = response.json()
    settings = data["settings"]
    assert settings["notifications_enabled"] is True
    assert settings["telegram_enabled"] is True
    assert settings["telegram_bot_token_masked"] != "123456:SECRET"
    assert settings["smtp_password_masked"] != "email-secret"
    assert "telegram_bot_token" not in settings
    assert "smtp_password" not in settings


def test_post_notification_settings_validates_telegram_config(tmp_path: Path):
    settings_path = tmp_path / "config" / "local_notification_settings.json"

    with (
        patch("web_dashboard.app.load_notification_settings", side_effect=lambda: _load_settings_from(settings_path)),
        patch("web_dashboard.app.save_notification_settings", side_effect=lambda settings: _save_settings_to(settings, settings_path)),
    ):
        response = client.post(
            "/api/settings/notifications",
            json={
                "notifications_enabled": True,
                "telegram_enabled": True,
            },
        )

    assert response.status_code == 400
    errors = response.json()["detail"]["errors"]
    assert "Telegram bot token is required when Telegram is enabled." in errors
    assert "Telegram chat ID is required when Telegram is enabled." in errors


def test_post_notification_settings_validates_email_config(tmp_path: Path):
    settings_path = tmp_path / "config" / "local_notification_settings.json"

    with (
        patch("web_dashboard.app.load_notification_settings", side_effect=lambda: _load_settings_from(settings_path)),
        patch("web_dashboard.app.save_notification_settings", side_effect=lambda settings: _save_settings_to(settings, settings_path)),
    ):
        response = client.post(
            "/api/settings/notifications",
            json={
                "notifications_enabled": True,
                "email_enabled": True,
                "smtp_port": "not-a-number",
            },
        )

    assert response.status_code == 400
    errors = response.json()["detail"]["errors"]
    assert "SMTP host is required when email is enabled." in errors
    assert "SMTP port must be a positive number." in errors
    assert "At least one recipient email is required when email is enabled." in errors


def test_post_notification_settings_saves_safe_settings(tmp_path: Path):
    settings_path = tmp_path / "config" / "local_notification_settings.json"

    with (
        patch("web_dashboard.app.load_notification_settings", side_effect=lambda: _load_settings_from(settings_path)),
        patch("web_dashboard.app.save_notification_settings", side_effect=lambda settings: _save_settings_to(settings, settings_path)),
    ):
        response = client.post(
            "/api/settings/notifications",
            json={
                "notifications_enabled": True,
                "windows_enabled": True,
                "email_enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_port": "587",
                "smtp_security": "starttls",
                "smtp_username": "printer@example.com",
                "smtp_password": "topsecret",
                "email_from": "printer@example.com",
                "email_to": "ops@example.com,qa@example.com",
                "email_send_screenshot": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["settings"]["smtp_password_masked"] != "topsecret"

    saved = notification_settings.load_notification_settings(settings_path)
    assert saved["NOTIFICATIONS_ENABLED"] is True
    assert saved["WINDOWS_NOTIFICATIONS_ENABLED"] is True
    assert saved["SMTP_PORT"] == 587
    assert saved["SMTP_PASSWORD"] == "topsecret"


def test_post_notification_settings_blank_secret_keeps_existing(tmp_path: Path):
    settings_path = tmp_path / "config" / "local_notification_settings.json"
    notification_settings.save_notification_settings(
        {
            "NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_BOT_TOKEN": "keep-me",
            "TELEGRAM_CHAT_ID": "chat-1",
        },
        path=settings_path,
    )

    with (
        patch("web_dashboard.app.load_notification_settings", side_effect=lambda: _load_settings_from(settings_path)),
        patch("web_dashboard.app.save_notification_settings", side_effect=lambda settings: _save_settings_to(settings, settings_path)),
    ):
        response = client.post(
            "/api/settings/notifications",
            json={
                "notifications_enabled": True,
                "telegram_enabled": True,
                "telegram_bot_token": "",
                "telegram_chat_id": "",
            },
        )

    assert response.status_code == 200
    saved = notification_settings.load_notification_settings(settings_path)
    assert saved["TELEGRAM_BOT_TOKEN"] == "keep-me"
    assert saved["TELEGRAM_CHAT_ID"] == "chat-1"


def test_notification_test_endpoint_uses_mocked_results_and_redacts_secrets(
    tmp_path: Path,
):
    settings_path = tmp_path / "config" / "local_notification_settings.json"
    notification_settings.save_notification_settings(
        {
            "NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_NOTIFICATIONS_ENABLED": True,
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "TELEGRAM_CHAT_ID": "secret-chat",
        },
        path=settings_path,
    )

    mocked_results = [
        NotificationResult(
            provider="telegram",
            destination_id="secret-chat",
            success=False,
            message="request failed for secret-token",
        ),
        NotificationResult(
            provider="email",
            destination_id="ops@example.com",
            success=True,
            message="ok",
        ),
    ]

    with (
        patch("web_dashboard.app.load_notification_settings", side_effect=lambda: _load_settings_from(settings_path)),
        patch("web_dashboard.app.send_test_notification", return_value=mocked_results) as mock_send,
    ):
        response = client.post(
            "/api/settings/notifications/test",
            json={
                "notifications_enabled": True,
                "telegram_enabled": True,
                "telegram_bot_token": "",
                "telegram_chat_id": "",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert mock_send.called
    assert data["success"] is True
    assert len(data["results"]) == 2
    assert "secret-token" not in str(data)
    assert "secret-chat" not in str(data)
