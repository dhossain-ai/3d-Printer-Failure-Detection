"""Tests for the Creality status CLI."""

from tools.read_creality_status import main


def test_main_returns_nonzero_without_url(capsys) -> None:
    """The CLI should require an explicit WebSocket URL."""

    assert main([]) != 0
    assert "Usage:" in capsys.readouterr().err
