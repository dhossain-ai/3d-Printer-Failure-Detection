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
