"""Read-only web UI inspection for Creality-style printer interfaces."""

from __future__ import annotations

import re
import sys
import argparse
from collections.abc import Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests


DEFAULT_TIMEOUT_SECONDS = 2.0
MAX_JS_FILES = 10
MAX_BYTES_PER_FILE = 1_000_000
MAX_ROOT_BYTES = 500_000
SNIPPET_CONTEXT_CHARS = 90
API_PREFIXES = (
    "api",
    "printer",
    "server",
    "system",
    "control",
    "status",
    "camera",
    "machine",
)
CONTROL_KEYWORDS = (
    "control",
    "pause",
    "resume",
    "stop",
    "cancel",
    "restart",
    "home",
    "move",
    "heat",
    "extrude",
    "retract",
    "gcode",
    "command",
)
COMMAND_DISCOVERY_KEYWORDS = (
    "ws://",
    "websocket",
    "send(",
    "json.stringify",
    "cmd",
    "command",
    "method",
    "light",
    "fan",
    "pause",
    "resume",
    "stop",
    "cancel",
    "print",
    "gcode",
    "nozzle",
    "bed",
    "temp",
    "ai",
    "video",
    "timelapse",
    "file",
    "upload",
)

ENDPOINT_PATTERN = re.compile(
    (
        r"""["'`]((?:https?://|wss?://)[^"'`\s<>]+|/"""
        r"""(?:api|printer|server|system|control|status|camera|machine)"""
        r"""[^"'`\s<>{}]*)["'`]"""
    ),
    re.IGNORECASE,
)
FETCH_PATTERN = re.compile(
    (
        r"""(?:fetch|axios\.(?:get|post|put|delete)|XMLHttpRequest|\.open)"""
        r"""\s*\([^)]{0,200}\)"""
    ),
    re.IGNORECASE,
)
WEBSOCKET_PATTERN = re.compile(
    r"""(?:wss?://[^"'`\s<>]+|new\s+WebSocket\s*\(\s*["'`]([^"'`]+)["'`])""",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WebUiAssets:
    """Static assets discovered in the root printer web UI HTML."""

    title: str | None
    script_srcs: list[str]
    stylesheet_hrefs: list[str]


@dataclass(frozen=True)
class JsInspection:
    """Inspection result for one same-origin JavaScript asset."""

    url: str
    fetched: bool
    note: str
    endpoints: list[str] = field(default_factory=list)
    websocket_candidates: list[str] = field(default_factory=list)
    fetch_references: list[str] = field(default_factory=list)
    command_snippets: list["CommandSnippet"] = field(default_factory=list)


@dataclass(frozen=True)
class CommandSnippet:
    """A command-looking static JavaScript snippet."""

    keyword: str
    snippet: str


@dataclass(frozen=True)
class WebUiInspection:
    """Read-only inspection result for a printer web UI."""

    root_url: str
    reachable: bool
    status_code: int | None
    assets: WebUiAssets
    endpoints: list[str]
    control_candidates: list[str]
    websocket_candidates: list[str]
    fetch_references: list[str]
    command_snippets: list[CommandSnippet]
    js_inspections: list[JsInspection]
    notes: list[str]


class WebUiHtmlParser(HTMLParser):
    """Small HTML parser for title, scripts, and stylesheet links."""

    def __init__(self) -> None:
        """Create an empty parser."""

        super().__init__()
        self.title: str | None = None
        self.script_srcs: list[str] = []
        self.stylesheet_hrefs: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        """Collect interesting tag attributes."""

        attr_map = {key.lower(): value or "" for key, value in attrs}
        tag_name = tag.lower()
        if tag_name == "title":
            self._in_title = True
            self._title_parts = []
        if tag_name == "script" and attr_map.get("src"):
            self.script_srcs.append(attr_map["src"])
        if tag_name == "link" and attr_map.get("href"):
            rel = attr_map.get("rel", "").lower()
            if "stylesheet" in rel:
                self.stylesheet_hrefs.append(attr_map["href"])

    def handle_endtag(self, tag: str) -> None:
        """Finish title collection."""

        if tag.lower() == "title" and self._in_title:
            title = " ".join("".join(self._title_parts).split())
            self.title = title or None
            self._in_title = False

    def handle_data(self, data: str) -> None:
        """Collect title text."""

        if self._in_title:
            self._title_parts.append(data)


def inspect_webui(
    host: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_js_files: int = MAX_JS_FILES,
    max_bytes_per_file: int = MAX_BYTES_PER_FILE,
) -> WebUiInspection:
    """Inspect a printer web UI using read-only GET requests."""

    root_url = build_root_url(host)
    root_text, status_code, note = fetch_text_limited(
        root_url,
        timeout=timeout,
        max_bytes=MAX_ROOT_BYTES,
    )
    if root_text is None:
        return WebUiInspection(
            root_url=root_url,
            reachable=False,
            status_code=status_code,
            assets=WebUiAssets(title=None, script_srcs=[], stylesheet_hrefs=[]),
            endpoints=[],
            control_candidates=[],
            websocket_candidates=[],
            fetch_references=[],
            command_snippets=[],
            js_inspections=[],
            notes=[note],
        )

    assets = parse_html_assets(root_text)
    endpoints = extract_endpoint_candidates(root_text)
    websocket_candidates = extract_websocket_candidates(root_text)
    fetch_references = extract_fetch_references(root_text)
    command_snippets = extract_command_snippets(root_text)
    js_inspections = inspect_same_origin_js(
        root_url=root_url,
        script_srcs=assets.script_srcs,
        timeout=timeout,
        max_files=max_js_files,
        max_bytes=max_bytes_per_file,
    )

    all_endpoints = endpoints[:]
    all_websockets = websocket_candidates[:]
    all_fetch_references = fetch_references[:]
    all_command_snippets = command_snippets[:]
    notes = [note]
    for js_result in js_inspections:
        all_endpoints.extend(js_result.endpoints)
        all_websockets.extend(js_result.websocket_candidates)
        all_fetch_references.extend(js_result.fetch_references)
        all_command_snippets.extend(js_result.command_snippets)
        if js_result.note:
            notes.append(f"{js_result.url}: {js_result.note}")

    unique_endpoints = sorted(set(all_endpoints))
    return WebUiInspection(
        root_url=root_url,
        reachable=True,
        status_code=status_code,
        assets=assets,
        endpoints=[
            endpoint
            for endpoint in unique_endpoints
            if not is_control_candidate(endpoint)
        ],
        control_candidates=[
            endpoint for endpoint in unique_endpoints if is_control_candidate(endpoint)
        ],
        websocket_candidates=sorted(set(all_websockets)),
        fetch_references=sorted(set(all_fetch_references)),
        command_snippets=dedupe_command_snippets(all_command_snippets),
        js_inspections=js_inspections,
        notes=notes,
    )


def build_root_url(host: str) -> str:
    """Build the root HTTP web UI URL for a host or IP."""

    normalized_host = normalize_host(host)
    return f"http://{normalized_host}/"


def normalize_host(host: str) -> str:
    """Return a host without scheme, path, or trailing slash."""

    stripped = host.strip()
    parsed = urlparse(stripped if "://" in stripped else f"//{stripped}")
    return (parsed.netloc or parsed.path).rstrip("/")


def parse_html_assets(html: str) -> WebUiAssets:
    """Parse title, script srcs, and stylesheet hrefs from HTML."""

    parser = WebUiHtmlParser()
    parser.feed(html)
    return WebUiAssets(
        title=parser.title,
        script_srcs=dedupe_preserve_order(parser.script_srcs),
        stylesheet_hrefs=dedupe_preserve_order(parser.stylesheet_hrefs),
    )


def inspect_same_origin_js(
    root_url: str,
    script_srcs: list[str],
    timeout: float,
    max_files: int,
    max_bytes: int,
) -> list[JsInspection]:
    """Fetch same-origin JavaScript assets and extract endpoint candidates."""

    results: list[JsInspection] = []
    for script_url in same_origin_script_urls(root_url, script_srcs)[:max_files]:
        js_text, _status_code, note = fetch_text_limited(
            script_url,
            timeout=timeout,
            max_bytes=max_bytes,
        )
        if js_text is None:
            results.append(JsInspection(url=script_url, fetched=False, note=note))
            continue

        results.append(
            JsInspection(
                url=script_url,
                fetched=True,
                note=note,
                endpoints=extract_endpoint_candidates(js_text),
                websocket_candidates=extract_websocket_candidates(js_text),
                fetch_references=extract_fetch_references(js_text),
                command_snippets=extract_command_snippets(js_text),
            )
        )

    return results


def same_origin_script_urls(root_url: str, script_srcs: list[str]) -> list[str]:
    """Return absolute same-origin script URLs only."""

    root = urlparse(root_url)
    urls: list[str] = []
    for script_src in script_srcs:
        absolute_url = urljoin(root_url, script_src)
        parsed = urlparse(absolute_url)
        if parsed.scheme in {"http", "https"} and parsed.netloc == root.netloc:
            urls.append(absolute_url)
    return dedupe_preserve_order(urls)


def fetch_text_limited(
    url: str,
    timeout: float,
    max_bytes: int,
) -> tuple[str | None, int | None, str]:
    """Fetch text with a GET request and a strict byte cap."""

    response: requests.Response | None = None
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        status_code = response.status_code
        chunks: list[bytes] = []
        total_bytes = 0
        truncated = False
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            remaining_bytes = max_bytes - total_bytes
            if remaining_bytes <= 0:
                truncated = True
                break
            chunks.append(chunk[:remaining_bytes])
            total_bytes += len(chunks[-1])
            if len(chunk) > remaining_bytes:
                truncated = True
                break

        response.raise_for_status()
        text = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        note = f"GET succeeded ({total_bytes} bytes read"
        note += ", truncated)" if truncated else ")"
        return text, status_code, note
    except requests.Timeout as exc:
        return None, None, f"timeout: {exc}"
    except requests.ConnectionError as exc:
        return None, None, f"connection error: {exc}"
    except requests.RequestException as exc:
        status_code = response.status_code if response is not None else None
        return None, status_code, f"request error: {exc}"
    except Exception as exc:
        status_code = response.status_code if response is not None else None
        return None, status_code, f"unexpected error: {exc}"
    finally:
        if response is not None:
            response.close()


def extract_endpoint_candidates(text: str) -> list[str]:
    """Extract API-looking path and URL candidates from text."""

    candidates = [match.group(1) for match in ENDPOINT_PATTERN.finditer(text)]
    return dedupe_preserve_order(
        candidate.rstrip(".,;")
        for candidate in candidates
        if is_api_like_candidate(candidate)
    )


def extract_websocket_candidates(text: str) -> list[str]:
    """Extract visible websocket candidates from text."""

    candidates: list[str] = []
    for match in WEBSOCKET_PATTERN.finditer(text):
        candidates.append(match.group(1) or match.group(0))
    return dedupe_preserve_order(candidate.strip() for candidate in candidates)


def extract_fetch_references(text: str) -> list[str]:
    """Extract visible fetch/ajax-looking call fragments."""

    return dedupe_preserve_order(
        " ".join(match.group(0).split()) for match in FETCH_PATTERN.finditer(text)
    )


def extract_command_snippets(
    text: str,
    context_chars: int = SNIPPET_CONTEXT_CHARS,
) -> list[CommandSnippet]:
    """Extract command-looking snippets with surrounding static context."""

    lowered_text = text.lower()
    snippets: list[CommandSnippet] = []
    for keyword in COMMAND_DISCOVERY_KEYWORDS:
        start_index = 0
        lowered_keyword = keyword.lower()
        while True:
            match_index = lowered_text.find(lowered_keyword, start_index)
            if match_index == -1:
                break
            snippet_start = max(0, match_index - context_chars)
            snippet_end = min(len(text), match_index + len(keyword) + context_chars)
            snippets.append(
                CommandSnippet(
                    keyword=keyword,
                    snippet=normalize_snippet(text[snippet_start:snippet_end]),
                )
            )
            start_index = match_index + len(keyword)

    return dedupe_command_snippets(snippets)


def normalize_snippet(snippet: str) -> str:
    """Normalize snippet whitespace for reports."""

    return " ".join(snippet.split())


def is_api_like_candidate(candidate: str) -> bool:
    """Return whether a string looks like a printer API path or URL."""

    parsed = urlparse(candidate)
    path = parsed.path if parsed.scheme else candidate
    path = path.lstrip("/")
    return any(
        path == prefix or path.startswith(f"{prefix}/") for prefix in API_PREFIXES
    )


def is_control_candidate(candidate: str) -> bool:
    """Return whether an endpoint candidate appears control-related."""

    lowered = candidate.lower()
    return any(keyword in lowered for keyword in CONTROL_KEYWORDS)


def print_report(inspection: WebUiInspection) -> None:
    """Print a clear read-only web UI inspection report."""

    print("PrintSentinel Printer Web UI Inspection")
    print(f"Root URL: {inspection.root_url}")
    print(f"Reachable: {'yes' if inspection.reachable else 'no'}")
    print(f"HTTP status: {inspection.status_code or '-'}")
    print(f"Title: {inspection.assets.title or '-'}")
    print()
    _print_list("Script assets", inspection.assets.script_srcs)
    _print_list("Stylesheet assets", inspection.assets.stylesheet_hrefs)
    _print_list("Fetch/ajax-looking references", inspection.fetch_references)
    _print_snippets("Command-looking snippets", inspection.command_snippets)
    _print_list("Possible read-only endpoints", inspection.endpoints)
    _print_list(
        "Possible control endpoints (candidate only - not called)",
        inspection.control_candidates,
    )
    _print_list("Websocket candidates", inspection.websocket_candidates)
    print("JavaScript files inspected:")
    if not inspection.js_inspections:
        print("  - none")
    for js_result in inspection.js_inspections:
        status = "fetched" if js_result.fetched else "not fetched"
        print(f"  - {js_result.url} ({status}): {js_result.note}")
    _print_list("Notes", inspection.notes)


def main(argv: list[str] | None = None) -> int:
    """Run read-only printer web UI inspection from command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Read-only printer web UI inspection.",
    )
    parser.add_argument("host", nargs="?")
    parser.add_argument("--max-js-files", type=int, default=MAX_JS_FILES)
    parser.add_argument("--max-js-bytes", type=int, default=MAX_BYTES_PER_FILE)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not args.host or not args.host.strip():
        parser.print_usage(sys.stderr)
        return 2

    inspection = inspect_webui(
        args.host,
        max_js_files=args.max_js_files,
        max_bytes_per_file=args.max_js_bytes,
    )
    print_report(inspection)
    return 0 if inspection.reachable else 1


def dedupe_preserve_order(values: Iterable[object]) -> list[str]:
    """Return unique non-empty strings while preserving order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            unique_values.append(text)
    return unique_values


def dedupe_command_snippets(snippets: Iterable[CommandSnippet]) -> list[CommandSnippet]:
    """Return unique snippets while preserving order."""

    seen: set[tuple[str, str]] = set()
    unique_snippets: list[CommandSnippet] = []
    for snippet in snippets:
        key = (snippet.keyword, snippet.snippet)
        if key not in seen:
            seen.add(key)
            unique_snippets.append(snippet)
    return unique_snippets


def _print_list(title: str, values: list[str]) -> None:
    """Print a titled list."""

    print(f"{title}:")
    if not values:
        print("  - none")
        return
    for value in values:
        print(f"  - {value}")


def _print_snippets(title: str, snippets: list[CommandSnippet]) -> None:
    """Print command-looking snippets."""

    print(f"{title}:")
    if not snippets:
        print("  - none")
        return
    for snippet in snippets:
        print(f"  - {snippet.keyword}: {snippet.snippet}")


if __name__ == "__main__":
    raise SystemExit(main())
