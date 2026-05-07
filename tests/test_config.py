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
