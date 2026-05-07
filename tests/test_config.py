"""Tests for environment-backed application configuration."""

import importlib

import config


def test_printer_camera_url_uses_prefixed_environment_first(monkeypatch) -> None:
    """Printer camera URL should follow the existing env precedence style."""

    monkeypatch.setenv("PRINTER_CAMERA_URL", "http://unprefixed/snapshot")
    monkeypatch.setenv("PRINTSENTINEL_PRINTER_CAMERA_URL", "http://prefixed/stream")

    reloaded_config = importlib.reload(config)

    assert reloaded_config.PRINTER_CAMERA_URL == "http://prefixed/stream"

    monkeypatch.delenv("PRINTER_CAMERA_URL")
    monkeypatch.delenv("PRINTSENTINEL_PRINTER_CAMERA_URL")
    importlib.reload(config)


def test_printer_camera_type_defaults_and_falls_back_to_stream(monkeypatch) -> None:
    """Printer camera type should default to stream and reject unknown values."""

    monkeypatch.delenv("PRINTER_CAMERA_TYPE", raising=False)
    monkeypatch.delenv("PRINTSENTINEL_PRINTER_CAMERA_TYPE", raising=False)
    reloaded_config = importlib.reload(config)
    assert reloaded_config.PRINTER_CAMERA_TYPE == "stream"

    monkeypatch.setenv("PRINTSENTINEL_PRINTER_CAMERA_TYPE", "snapshot")
    reloaded_config = importlib.reload(config)
    assert reloaded_config.PRINTER_CAMERA_TYPE == "snapshot"

    monkeypatch.setenv("PRINTSENTINEL_PRINTER_CAMERA_TYPE", "unsafe")
    reloaded_config = importlib.reload(config)
    assert reloaded_config.PRINTER_CAMERA_TYPE == "stream"

    monkeypatch.delenv("PRINTSENTINEL_PRINTER_CAMERA_TYPE")
    importlib.reload(config)


def test_model_device_defaults_to_auto_and_rejects_unknown_values(monkeypatch) -> None:
    """Model device should default to auto and validate explicit values."""

    monkeypatch.delenv("MODEL_DEVICE", raising=False)
    monkeypatch.delenv("PRINTSENTINEL_MODEL_DEVICE", raising=False)
    reloaded_config = importlib.reload(config)
    assert reloaded_config.MODEL_DEVICE == "auto"

    for model_device in ("cpu", "cuda", "0"):
        monkeypatch.setenv("PRINTSENTINEL_MODEL_DEVICE", model_device)
        reloaded_config = importlib.reload(config)
        assert reloaded_config.MODEL_DEVICE == model_device

    monkeypatch.setenv("PRINTSENTINEL_MODEL_DEVICE", "gpu")
    reloaded_config = importlib.reload(config)
    assert reloaded_config.MODEL_DEVICE == "auto"

    monkeypatch.delenv("PRINTSENTINEL_MODEL_DEVICE")
    importlib.reload(config)


def test_creality_status_config_uses_prefixed_environment_first(monkeypatch) -> None:
    """Creality status config should follow existing env precedence."""

    monkeypatch.delenv("CREALITY_WS_URL", raising=False)
    monkeypatch.delenv("PRINTSENTINEL_CREALITY_WS_URL", raising=False)
    monkeypatch.delenv("CREALITY_STATUS_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("PRINTSENTINEL_CREALITY_STATUS_TIMEOUT_SECONDS", raising=False)
    reloaded_config = importlib.reload(config)
    assert reloaded_config.CREALITY_WS_URL == ""
    assert reloaded_config.CREALITY_STATUS_TIMEOUT_SECONDS == 5.0

    monkeypatch.setenv("CREALITY_WS_URL", "ws://unprefixed:9999")
    monkeypatch.setenv("PRINTSENTINEL_CREALITY_WS_URL", "ws://prefixed:9999")
    monkeypatch.setenv("PRINTSENTINEL_CREALITY_STATUS_TIMEOUT_SECONDS", "7.5")

    reloaded_config = importlib.reload(config)

    assert reloaded_config.CREALITY_WS_URL == "ws://prefixed:9999"
    assert reloaded_config.CREALITY_STATUS_TIMEOUT_SECONDS == 7.5

    monkeypatch.delenv("CREALITY_WS_URL")
    monkeypatch.delenv("PRINTSENTINEL_CREALITY_WS_URL")
    monkeypatch.delenv("PRINTSENTINEL_CREALITY_STATUS_TIMEOUT_SECONDS")
    importlib.reload(config)
