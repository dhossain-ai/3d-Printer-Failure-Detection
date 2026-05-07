"""Read-only static JavaScript scanner for Creality command discovery."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tools.inspect_printer_webui import (  # noqa: E402
    DEFAULT_TIMEOUT_SECONDS,
    MAX_BYTES_PER_FILE,
    MAX_JS_FILES,
    MAX_ROOT_BYTES,
    CommandSnippet,
    WebUiAssets,
    build_root_url,
    extract_command_snippets,
    fetch_text_limited,
    parse_html_assets,
    same_origin_script_urls,
)


STATUS_FIELD_KEYWORDS = (
    "nozzleTemp",
    "bedTemp0",
    "boxTemp",
    "deviceState",
    "state",
    "printProgress",
    "dProgress",
    "printFileName",
    "printLeftTime",
    "lightSw",
    "fan",
    "aiDetection",
    "aiPausePrint",
    "video",
    "hostname",
    "model",
)
WEBSOCKET_KEYWORDS = ("ws://", "websocket", "new websocket")
COMMAND_NAME_KEYWORDS = (
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
)
CONTROL_PAYLOAD_KEYWORDS = ("send(", "json.stringify", "cmd", "command", "method")
FILE_API_KEYWORDS = ("file", "upload", "printFileName", "gcode")
CAMERA_VIDEO_KEYWORDS = ("camera", "video", "timelapse")


@dataclass(frozen=True)
class JsScanSource:
    """One fetched source scanned for command-looking JavaScript."""

    name: str
    url: str
    fetched: bool
    note: str
    text: str = ""


@dataclass(frozen=True)
class CategorizedFinding:
    """One categorized scanner finding."""

    category: str
    source: str
    keyword: str
    snippet: str


@dataclass(frozen=True)
class CommandScanResult:
    """Read-only Creality JavaScript command scan result."""

    root_url: str
    reachable: bool
    assets: WebUiAssets
    sources: list[JsScanSource]
    findings: dict[str, list[CategorizedFinding]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def scan_creality_js_commands(
    host: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_js_files: int = MAX_JS_FILES,
    max_js_bytes: int = MAX_BYTES_PER_FILE,
) -> CommandScanResult:
    """Fetch root/same-origin JS and scan statically for command clues."""

    root_url = build_root_url(host)
    root_text, _status_code, root_note = fetch_text_limited(
        root_url,
        timeout=timeout,
        max_bytes=MAX_ROOT_BYTES,
    )
    if root_text is None:
        return CommandScanResult(
            root_url=root_url,
            reachable=False,
            assets=WebUiAssets(title=None, script_srcs=[], stylesheet_hrefs=[]),
            sources=[],
            notes=[root_note],
        )

    assets = parse_html_assets(root_text)
    sources = [
        JsScanSource(
            name="root HTML",
            url=root_url,
            fetched=True,
            note=root_note,
            text=root_text,
        )
    ]
    for script_url in same_origin_script_urls(
        root_url,
        assets.script_srcs,
    )[:max_js_files]:
        js_text, _status_code, note = fetch_text_limited(
            script_url,
            timeout=timeout,
            max_bytes=max_js_bytes,
        )
        sources.append(
            JsScanSource(
                name=Path(urlparse(script_url).path).name or script_url,
                url=script_url,
                fetched=js_text is not None,
                note=note,
                text=js_text or "",
            )
        )

    findings = categorize_sources(sources)
    return CommandScanResult(
        root_url=root_url,
        reachable=True,
        assets=assets,
        sources=sources,
        findings=findings,
        notes=[source.note for source in sources if source.note],
    )


def categorize_sources(
    sources: list[JsScanSource],
) -> dict[str, list[CategorizedFinding]]:
    """Categorize static command-discovery findings by source text."""

    categorized: dict[str, list[CategorizedFinding]] = {
        "websocket setup": [],
        "status fields": [],
        "possible command names": [],
        "possible control payloads": [],
        "possible file APIs": [],
        "possible camera/video APIs": [],
    }
    for source in sources:
        if not source.fetched:
            continue
        snippets = extract_static_snippets(source.text)
        _add_keyword_findings(
            categorized["websocket setup"],
            source,
            snippets,
            WEBSOCKET_KEYWORDS,
        )
        _add_keyword_findings(
            categorized["status fields"],
            source,
            snippets,
            STATUS_FIELD_KEYWORDS,
        )
        _add_keyword_findings(
            categorized["possible command names"],
            source,
            snippets,
            COMMAND_NAME_KEYWORDS,
        )
        _add_keyword_findings(
            categorized["possible control payloads"],
            source,
            snippets,
            CONTROL_PAYLOAD_KEYWORDS,
        )
        _add_keyword_findings(
            categorized["possible file APIs"],
            source,
            snippets,
            FILE_API_KEYWORDS,
        )
        _add_keyword_findings(
            categorized["possible camera/video APIs"],
            source,
            snippets,
            CAMERA_VIDEO_KEYWORDS,
        )

    return {
        category: dedupe_findings(findings)
        for category, findings in categorized.items()
    }


def extract_static_snippets(text: str) -> list[CommandSnippet]:
    """Extract all snippets useful for static command discovery."""

    snippets = extract_command_snippets(text)
    snippets.extend(_extract_keyword_snippets(text, STATUS_FIELD_KEYWORDS))
    return _dedupe_snippets(snippets)


def print_report(result: CommandScanResult) -> None:
    """Print a clear read-only command discovery report."""

    print("PrintSentinel Creality JavaScript Command Scan")
    print(f"Root URL: {result.root_url}")
    print(f"Reachable: {'yes' if result.reachable else 'no'}")
    print(f"Title: {result.assets.title or '-'}")
    print()
    print("Fetched sources:")
    if not result.sources:
        print("  - none")
    for source in result.sources:
        status = "fetched" if source.fetched else "not fetched"
        print(f"  - {source.url} ({status}): {source.note}")

    for category, findings in result.findings.items():
        print()
        print(f"{category.title()}:")
        if not findings:
            print("  - none")
            continue
        for finding in findings:
            print(f"  - {finding.source} [{finding.keyword}]: {finding.snippet}")

    print()
    print("Safety notes:")
    print("  - GET-only static scan; no discovered endpoint is called.")
    print("  - No WebSocket connection is opened and no command payload is sent.")
    print("  - Treat all findings as candidates until manually verified.")


def main(argv: list[str] | None = None) -> int:
    """Run read-only static Creality JavaScript command scanning."""

    parser = argparse.ArgumentParser(
        description="Read-only Creality JavaScript command scanner.",
    )
    parser.add_argument("host", nargs="?")
    parser.add_argument("--max-js-files", type=int, default=MAX_JS_FILES)
    parser.add_argument("--max-js-bytes", type=int, default=MAX_BYTES_PER_FILE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not args.host or not args.host.strip():
        parser.print_usage(sys.stderr)
        return 2

    result = scan_creality_js_commands(
        args.host,
        timeout=args.timeout,
        max_js_files=args.max_js_files,
        max_js_bytes=args.max_js_bytes,
    )
    print_report(result)
    return 0 if result.reachable else 1


def _add_keyword_findings(
    findings: list[CategorizedFinding],
    source: JsScanSource,
    snippets: list[CommandSnippet],
    keywords: tuple[str, ...],
) -> None:
    """Add snippets whose keyword or text matches one category."""

    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    for snippet in snippets:
        lowered_snippet = snippet.snippet.lower()
        lowered_keyword = snippet.keyword.lower()
        if lowered_keyword in lowered_keywords or any(
            keyword in lowered_snippet for keyword in lowered_keywords
        ):
            findings.append(
                CategorizedFinding(
                    category="",
                    source=source.url,
                    keyword=snippet.keyword,
                    snippet=snippet.snippet,
                )
            )


def _extract_keyword_snippets(
    text: str,
    keywords: tuple[str, ...],
    context_chars: int = 90,
) -> list[CommandSnippet]:
    """Extract snippets for a specific keyword set."""

    lowered_text = text.lower()
    snippets: list[CommandSnippet] = []
    for keyword in keywords:
        lowered_keyword = keyword.lower()
        start_index = 0
        while True:
            match_index = lowered_text.find(lowered_keyword, start_index)
            if match_index == -1:
                break
            snippet_start = max(0, match_index - context_chars)
            snippet_end = min(len(text), match_index + len(keyword) + context_chars)
            snippets.append(
                CommandSnippet(
                    keyword=keyword,
                    snippet=" ".join(text[snippet_start:snippet_end].split()),
                )
            )
            start_index = match_index + len(keyword)
    return snippets


def _dedupe_snippets(snippets: list[CommandSnippet]) -> list[CommandSnippet]:
    """Return unique snippets while preserving order."""

    seen: set[tuple[str, str]] = set()
    unique_snippets: list[CommandSnippet] = []
    for snippet in snippets:
        key = (snippet.keyword, snippet.snippet)
        if key not in seen:
            seen.add(key)
            unique_snippets.append(snippet)
    return unique_snippets


def dedupe_findings(findings: list[CategorizedFinding]) -> list[CategorizedFinding]:
    """Return unique findings while preserving order."""

    seen: set[tuple[str, str, str]] = set()
    unique_findings: list[CategorizedFinding] = []
    for finding in findings:
        key = (finding.source, finding.keyword, finding.snippet)
        if key not in seen:
            seen.add(key)
            unique_findings.append(
                CategorizedFinding(
                    category=finding.category,
                    source=finding.source,
                    keyword=finding.keyword,
                    snippet=finding.snippet,
                )
            )
    return unique_findings


if __name__ == "__main__":
    raise SystemExit(main())
