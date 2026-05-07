"""Tests for the read-only Creality JavaScript command scanner."""

from pathlib import Path

from tools.scan_creality_js_commands import (
    categorize_sources,
    scan_creality_js_commands,
)


class FakeResponse:
    """Small streamed response stand-in."""

    def __init__(self, text: str) -> None:
        """Create a fake response."""

        self._content = text.encode("utf-8")
        self.status_code = 200
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, chunk_size: int) -> object:
        """Yield content in one chunk."""

        yield self._content

    def raise_for_status(self) -> None:
        """No-op for successful fake responses."""

    def close(self) -> None:
        """Record close."""

        self.closed = True


def test_js_scanner_extracts_command_looking_snippets() -> None:
    """Static categorization should find command names and status fields."""

    sources = [
        _source(
            """
            const status = {nozzleTemp: "25.0", bedTemp0: "24.0"};
            const payload = {cmd: "set_light", light: true};
            """,
        )
    ]

    findings = categorize_sources(sources)

    assert any(
        "set_light" in finding.snippet
        for finding in findings["possible command names"]
    )
    assert any(
        "nozzleTemp" in finding.snippet for finding in findings["status fields"]
    )


def test_js_scanner_detects_websocket_send_patterns() -> None:
    """Static categorization should surface WebSocket setup and send calls."""

    sources = [
        _source(
            """
            const ws = new WebSocket("ws://" + host + ":9999");
            ws.send(JSON.stringify({cmd: "light", light: 1}));
            """,
        )
    ]

    findings = categorize_sources(sources)

    assert any("WebSocket" in finding.snippet for finding in findings["websocket setup"])
    assert any(
        "JSON.stringify" in finding.snippet
        for finding in findings["possible control payloads"]
    )
    assert any("send(" in finding.snippet for finding in findings["possible control payloads"])


def test_scanner_respects_max_byte_limit(monkeypatch) -> None:
    """Command text beyond the byte cap should not be scanned."""

    html = '<script src="/app.js"></script>'
    js = "x" * 40 + ' ws.send(JSON.stringify({cmd: "stop"}));'
    responses = {
        "http://192.168.137.211/": FakeResponse(html),
        "http://192.168.137.211/app.js": FakeResponse(js),
    }

    monkeypatch.setattr(
        "tools.inspect_printer_webui.requests.get",
        lambda url, **kwargs: responses[url],
    )

    result = scan_creality_js_commands(
        "192.168.137.211",
        max_js_bytes=20,
    )

    assert result.reachable
    assert result.sources[1].note == "GET succeeded (20 bytes read, truncated)"
    assert result.findings["possible control payloads"] == []


def test_scanner_fetches_same_origin_assets_only(monkeypatch) -> None:
    """Scanner should ignore cross-origin script assets."""

    html = """
    <script src="/app.js"></script>
    <script src="http://external.local/app.js"></script>
    """
    js = 'const ws = "ws://printer:9999";'
    responses = {
        "http://192.168.137.211/": FakeResponse(html),
        "http://192.168.137.211/app.js": FakeResponse(js),
    }
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url, kwargs))
        return responses[url]

    def fail_mutating_method(*args: object, **kwargs: object) -> None:
        raise AssertionError("scanner must use GET only")

    monkeypatch.setattr("tools.inspect_printer_webui.requests.get", fake_get)
    monkeypatch.setattr(
        "tools.inspect_printer_webui.requests.post",
        fail_mutating_method,
    )
    monkeypatch.setattr(
        "tools.inspect_printer_webui.requests.put",
        fail_mutating_method,
    )
    monkeypatch.setattr(
        "tools.inspect_printer_webui.requests.delete",
        fail_mutating_method,
    )

    result = scan_creality_js_commands("192.168.137.211")

    assert [call[0] for call in calls] == [
        "http://192.168.137.211/",
        "http://192.168.137.211/app.js",
    ]
    assert result.sources[1].url == "http://192.168.137.211/app.js"


def test_new_static_tools_do_not_send_commands() -> None:
    """Static discovery tools should not contain WebSocket send execution."""

    root = Path(__file__).resolve().parents[1]
    scanner_text = (root / "tools" / "scan_creality_js_commands.py").read_text()
    inspector_text = (root / "tools" / "inspect_printer_webui.py").read_text()

    assert ".send(" not in scanner_text
    assert "create_connection" not in scanner_text
    assert ".send(" not in inspector_text
    assert "create_connection" not in inspector_text


def _source(text: str):
    """Build a fetched scanner source for categorization tests."""

    from tools.scan_creality_js_commands import JsScanSource

    return JsScanSource(
        name="app.js",
        url="http://printer/app.js",
        fetched=True,
        note="ok",
        text=text,
    )
