"""Tests for the read-only printer web UI inspector."""

import requests

from tools.inspect_printer_webui import (
    extract_command_snippets,
    extract_endpoint_candidates,
    extract_fetch_references,
    inspect_webui,
    parse_html_assets,
    same_origin_script_urls,
)


class FakeResponse:
    """Small streamed response stand-in."""

    def __init__(
        self,
        text: str = "",
        status_code: int = 200,
        error: requests.RequestException | None = None,
    ) -> None:
        """Create a fake response."""

        self._content = text.encode("utf-8")
        self.status_code = status_code
        self.error = error
        self.encoding = "utf-8"
        self.closed = False
        self.iter_content_calls: list[int] = []

    def iter_content(self, chunk_size: int) -> object:
        """Yield content in one chunk."""

        self.iter_content_calls.append(chunk_size)
        yield self._content

    def raise_for_status(self) -> None:
        """Raise the configured request error."""

        if self.error is not None:
            raise self.error

    def close(self) -> None:
        """Record close."""

        self.closed = True


def test_parse_html_assets_extracts_title_scripts_and_stylesheets() -> None:
    """HTML parsing should find basic document assets."""

    html = """
    <html>
      <head>
        <title> Creality K1C </title>
        <link rel="stylesheet" href="/assets/app.css">
        <script src="/assets/app.js"></script>
      </head>
    </html>
    """

    assets = parse_html_assets(html)

    assert assets.title == "Creality K1C"
    assert assets.script_srcs == ["/assets/app.js"]
    assert assets.stylesheet_hrefs == ["/assets/app.css"]


def test_extracts_js_endpoint_and_fetch_candidates() -> None:
    """Static text scanning should find endpoint-looking strings."""

    js_text = """
    fetch("/api/status");
    axios.get('/printer/info');
    fetch("/control/home");
    const ws = "ws://printer.local/websocket";
    """

    assert extract_endpoint_candidates(js_text) == [
        "/api/status",
        "/printer/info",
        "/control/home",
    ]
    assert extract_fetch_references(js_text) == [
        'fetch("/api/status")',
        "axios.get('/printer/info')",
        'fetch("/control/home")',
    ]


def test_extracts_command_looking_snippets_with_context() -> None:
    """Inspector should surface command-looking JavaScript context."""

    js_text = """
    const payload = JSON.stringify({cmd: "set_light", light: true});
    socket.send(payload);
    """

    snippets = extract_command_snippets(js_text)

    assert any(snippet.keyword == "json.stringify" for snippet in snippets)
    assert any(snippet.keyword == "cmd" for snippet in snippets)
    assert any("set_light" in snippet.snippet for snippet in snippets)


def test_same_origin_filtering_keeps_only_same_host_scripts() -> None:
    """Only same-host JavaScript assets should be fetched."""

    scripts = [
        "/assets/app.js",
        "http://192.168.137.211/vendor.js",
        "https://cdn.example.com/lib.js",
        "http://other.local/app.js",
    ]

    assert same_origin_script_urls("http://192.168.137.211/", scripts) == [
        "http://192.168.137.211/assets/app.js",
        "http://192.168.137.211/vendor.js",
    ]


def test_inspect_webui_fetches_root_and_same_origin_js_only(monkeypatch) -> None:
    """Inspection should GET root and limited same-origin JS assets."""

    html = """
    <title>K1C</title>
    <script src="/app.js"></script>
    <script src="http://external.local/ignored.js"></script>
    <link rel="stylesheet" href="/app.css">
    <script>fetch('/api/status');</script>
    """
    js = """
    fetch("/printer/info");
    fetch("/control/stop");
    socket.send(JSON.stringify({cmd: "stop"}));
    const socket = new WebSocket("ws://192.168.137.211/socket");
    """
    responses = {
        "http://192.168.137.211/": FakeResponse(html),
        "http://192.168.137.211/app.js": FakeResponse(js),
    }
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        calls.append((url, kwargs))
        return responses[url]

    def fail_mutating_method(*args: object, **kwargs: object) -> None:
        raise AssertionError("inspector must not use mutating HTTP methods")

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

    inspection = inspect_webui("192.168.137.211", timeout=0.5)

    assert inspection.reachable
    assert inspection.assets.title == "K1C"
    assert inspection.assets.script_srcs == [
        "/app.js",
        "http://external.local/ignored.js",
    ]
    assert inspection.endpoints == ["/api/status", "/printer/info"]
    assert inspection.control_candidates == ["/control/stop"]
    assert inspection.websocket_candidates == ["ws://192.168.137.211/socket"]
    assert any(
        snippet.keyword == "send(" and '"stop"' in snippet.snippet
        for snippet in inspection.command_snippets
    )
    assert calls == [
        ("http://192.168.137.211/", {"timeout": 0.5, "stream": True}),
        ("http://192.168.137.211/app.js", {"timeout": 0.5, "stream": True}),
    ]
    assert responses["http://192.168.137.211/"].closed
    assert responses["http://192.168.137.211/app.js"].closed


def test_inspect_webui_handles_timeout_as_unreachable(monkeypatch) -> None:
    """Root timeout should produce a clear unreachable inspection."""

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        raise requests.Timeout("web UI timed out")

    monkeypatch.setattr("tools.inspect_printer_webui.requests.get", fake_get)

    inspection = inspect_webui("192.168.137.211", timeout=0.5)

    assert not inspection.reachable
    assert inspection.status_code is None
    assert inspection.notes == ["timeout: web UI timed out"]


def test_inspect_webui_records_js_fetch_failures(monkeypatch) -> None:
    """JS timeout should be reported without failing the root inspection."""

    html = '<title>K1C</title><script src="/app.js"></script>'

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        if url.endswith("/app.js"):
            raise requests.Timeout("js timed out")
        return FakeResponse(html)

    monkeypatch.setattr("tools.inspect_printer_webui.requests.get", fake_get)

    inspection = inspect_webui("192.168.137.211", timeout=0.5)

    assert inspection.reachable
    assert len(inspection.js_inspections) == 1
    assert not inspection.js_inspections[0].fetched
    assert inspection.js_inspections[0].note == "timeout: js timed out"
