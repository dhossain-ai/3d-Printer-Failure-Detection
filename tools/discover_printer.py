"""Read-only LAN endpoint discovery for PrintSentinel printers."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


DEFAULT_TIMEOUT_SECONDS = 2.0
STREAM_SAMPLE_BYTES = 256


@dataclass(frozen=True)
class EndpointProbe:
    """A single read-only endpoint probe."""

    url: str
    is_stream: bool = False


@dataclass(frozen=True)
class ProbeResult:
    """Result from one read-only endpoint probe."""

    url: str
    reachable: bool
    status_code: int | None
    content_type: str | None
    classification: str
    note: str


def build_default_probes(host: str) -> list[EndpointProbe]:
    """Build the default safe endpoint probes for a printer host or IP."""

    normalized_host = _normalize_host(host)
    return [
        EndpointProbe(f"http://{normalized_host}/"),
        EndpointProbe(f"http://{normalized_host}:7125/server/info"),
        EndpointProbe(f"http://{normalized_host}:7125/printer/info"),
        EndpointProbe(
            f"http://{normalized_host}:7125/printer/objects/query?print_stats"
        ),
        EndpointProbe(f"http://{normalized_host}:8000/"),
        EndpointProbe(f"http://{normalized_host}:4408/webcam/?action=snapshot"),
        EndpointProbe(
            f"http://{normalized_host}:4408/webcam/?action=stream",
            is_stream=True,
        ),
        EndpointProbe(f"http://{normalized_host}:8080/?action=snapshot"),
        EndpointProbe(
            f"http://{normalized_host}:8080/?action=stream",
            is_stream=True,
        ),
    ]


def classify_response(
    probe: EndpointProbe,
    response: requests.Response,
    sample_bytes: bytes | None = None,
) -> str:
    """Classify a reachable endpoint from headers and a small optional sample."""

    content_type = _content_type(response).lower()
    sample = sample_bytes or b""
    url = probe.url.lower()

    if "multipart/x-mixed-replace" in content_type:
        return "camera_stream"
    if probe.is_stream and _looks_like_multipart_stream(sample):
        return "camera_stream"
    if content_type.startswith("image/") or _looks_like_image(sample):
        return "camera_snapshot"
    if _is_moonraker_url(url) and (
        "json" in content_type or _looks_like_json(sample)
    ):
        return "moonraker_api"
    if "text/html" in content_type:
        return "web_ui"

    return "unknown"


def probe_endpoint(probe: EndpointProbe, timeout: float) -> ProbeResult:
    """Probe one endpoint with a safe read-only GET request."""

    response: requests.Response | None = None
    sample_bytes: bytes | None = None
    try:
        response = requests.get(
            probe.url,
            timeout=timeout,
            stream=probe.is_stream,
        )
        if probe.is_stream:
            sample_bytes = _read_stream_sample(response)
        else:
            sample_bytes = response.content[:STREAM_SAMPLE_BYTES]

        return ProbeResult(
            url=probe.url,
            reachable=True,
            status_code=response.status_code,
            content_type=_content_type(response) or None,
            classification=classify_response(probe, response, sample_bytes),
            note="HTTP response received",
        )
    except requests.Timeout as exc:
        return _unavailable_result(probe, f"timeout: {exc}")
    except requests.ConnectionError as exc:
        return _unavailable_result(probe, f"connection error: {exc}")
    except requests.RequestException as exc:
        return _unavailable_result(probe, f"request error: {exc}")
    except Exception as exc:
        return _unavailable_result(probe, f"unexpected error: {exc}")
    finally:
        if response is not None:
            response.close()


def print_report(results: list[ProbeResult]) -> None:
    """Print a clear discovery report for endpoint probe results."""

    headers = [
        "URL",
        "Reachable",
        "Status",
        "Content-Type",
        "Classification",
        "Note",
    ]
    rows = [
        [
            result.url,
            "yes" if result.reachable else "no",
            str(result.status_code) if result.status_code is not None else "-",
            result.content_type or "-",
            result.classification,
            result.note,
        ]
        for result in results
    ]
    widths = [
        max(len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]

    print(_format_row(headers, widths))
    print(_format_row(["-" * width for width in widths], widths))
    for row in rows:
        print(_format_row(row, widths))


def main(argv: list[str] | None = None) -> int:
    """Run read-only printer discovery from command-line arguments."""

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or not args[0].strip():
        print("Usage: python tools/discover_printer.py <host-or-ip>", file=sys.stderr)
        return 2

    probes = build_default_probes(args[0])
    results = [probe_endpoint(probe, DEFAULT_TIMEOUT_SECONDS) for probe in probes]
    print_report(results)
    return 0


def _normalize_host(host: str) -> str:
    """Return a host without scheme, path, or trailing slash."""

    stripped = host.strip()
    parsed = urlparse(stripped if "://" in stripped else f"//{stripped}")
    return (parsed.netloc or parsed.path).rstrip("/")


def _content_type(response: requests.Response) -> str:
    """Return the response content type header without parameters."""

    return response.headers.get("Content-Type", "").split(";", maxsplit=1)[0].strip()


def _read_stream_sample(response: requests.Response) -> bytes:
    """Read at most a tiny initial stream chunk and stop."""

    for chunk in response.iter_content(chunk_size=STREAM_SAMPLE_BYTES):
        return chunk[:STREAM_SAMPLE_BYTES]
    return b""


def _looks_like_multipart_stream(sample: bytes) -> bool:
    """Return whether bytes look like the beginning of an MJPEG stream."""

    stripped = sample.lstrip()
    return stripped.startswith(b"--") and b"content-type:" in stripped.lower()


def _looks_like_image(sample: bytes) -> bool:
    """Return whether bytes look like a common image payload."""

    return sample.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF87a", b"GIF89a"))


def _looks_like_json(sample: bytes) -> bool:
    """Return whether bytes look like a JSON object or array."""

    stripped = sample.lstrip()
    return stripped.startswith((b"{", b"["))


def _is_moonraker_url(url: str) -> bool:
    """Return whether the URL targets known read-only Moonraker endpoints."""

    return ":7125/" in url and (
        "/server/info" in url
        or "/printer/info" in url
        or "/printer/objects/query?print_stats" in url
    )


def _unavailable_result(probe: EndpointProbe, note: str) -> ProbeResult:
    """Build an unavailable result for a failed probe."""

    return ProbeResult(
        url=probe.url,
        reachable=False,
        status_code=None,
        content_type=None,
        classification="unavailable",
        note=note,
    )


def _format_row(values: list[str], widths: list[int]) -> str:
    """Format a report row."""

    return " | ".join(value.ljust(widths[index]) for index, value in enumerate(values))


if __name__ == "__main__":
    raise SystemExit(main())
