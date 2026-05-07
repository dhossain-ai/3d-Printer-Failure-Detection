"""Tests for the read-only printer discovery utility."""

import requests

from tools.discover_printer import (
    EndpointProbe,
    build_default_probes,
    classify_response,
    main,
    probe_endpoint,
)


class FakeResponse:
    """Small requests.Response stand-in for discovery tests."""

    def __init__(
        self,
        status_code: int = 200,
        content_type: str = "",
        content: bytes = b"",
        stream_chunks: list[bytes] | None = None,
    ) -> None:
        """Create a fake response with optional stream chunks."""

        self.status_code = status_code
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.content = content
        self.stream_chunks = stream_chunks or []
        self.closed = False
        self.iter_content_calls: list[int] = []
        self.chunks_read = 0

    def iter_content(self, chunk_size: int) -> object:
        """Yield stream chunks and fail if the caller keeps reading."""

        self.iter_content_calls.append(chunk_size)
        for chunk in self.stream_chunks:
            self.chunks_read += 1
            yield chunk
        raise AssertionError("stream probe read past the tiny initial sample")

    def close(self) -> None:
        """Record that the response was closed."""

        self.closed = True


def test_build_default_probes_builds_expected_urls_from_host() -> None:
    """Default probes should target the requested host without hardcoding an IP."""

    probes = build_default_probes("192.168.12.236")

    assert [probe.url for probe in probes] == [
        "http://192.168.12.236/",
        "http://192.168.12.236:7125/server/info",
        "http://192.168.12.236:7125/printer/info",
        "http://192.168.12.236:7125/printer/objects/query?print_stats",
        "http://192.168.12.236:8000/",
        "http://192.168.12.236:4408/webcam/?action=snapshot",
        "http://192.168.12.236:4408/webcam/?action=stream",
        "http://192.168.12.236:8080/?action=snapshot",
        "http://192.168.12.236:8080/?action=stream",
    ]


def test_classifies_moonraker_json_as_moonraker_api() -> None:
    """Known read-only Moonraker JSON endpoints should be classified."""

    probe = EndpointProbe("http://printer.local:7125/server/info")
    response = FakeResponse(content_type="application/json", content=b'{"result": {}}')

    assert classify_response(probe, response, response.content) == "moonraker_api"


def test_classifies_image_response_as_camera_snapshot() -> None:
    """Image responses should be classified as camera snapshots."""

    probe = EndpointProbe("http://printer.local:8080/?action=snapshot")
    response = FakeResponse(content_type="image/jpeg", content=b"\xff\xd8\xff")

    assert classify_response(probe, response, response.content) == "camera_snapshot"


def test_classifies_multipart_response_as_camera_stream() -> None:
    """MJPEG multipart responses should be classified as camera streams."""

    probe = EndpointProbe("http://printer.local:8080/?action=stream", is_stream=True)
    response = FakeResponse(content_type="multipart/x-mixed-replace")

    assert classify_response(probe, response) == "camera_stream"


def test_probe_endpoint_handles_timeout_as_unavailable(monkeypatch) -> None:
    """Timeouts should be reported as unavailable results."""

    def fake_get(*args: object, **kwargs: object) -> FakeResponse:
        raise requests.Timeout("read timed out")

    monkeypatch.setattr("tools.discover_printer.requests.get", fake_get)

    result = probe_endpoint(EndpointProbe("http://printer.local/"), timeout=0.5)

    assert not result.reachable
    assert result.classification == "unavailable"
    assert "timeout" in result.note


def test_probe_endpoint_handles_connection_error_as_unavailable(monkeypatch) -> None:
    """Connection errors should be reported as unavailable results."""

    def fake_get(*args: object, **kwargs: object) -> FakeResponse:
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("tools.discover_printer.requests.get", fake_get)

    result = probe_endpoint(EndpointProbe("http://printer.local/"), timeout=0.5)

    assert not result.reachable
    assert result.classification == "unavailable"
    assert "connection error" in result.note


def test_stream_probe_reads_tiny_sample_and_closes_response(monkeypatch) -> None:
    """Stream probes should use stream=True, read one small chunk, and close."""

    calls: list[dict[str, object]] = []
    response = FakeResponse(
        content_type="multipart/x-mixed-replace",
        stream_chunks=[b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"],
    )

    def fake_get(*args: object, **kwargs: object) -> FakeResponse:
        calls.append(kwargs)
        return response

    monkeypatch.setattr("tools.discover_printer.requests.get", fake_get)

    result = probe_endpoint(
        EndpointProbe("http://printer.local:8080/?action=stream", is_stream=True),
        timeout=0.5,
    )

    assert result.reachable
    assert result.classification == "camera_stream"
    assert calls == [{"timeout": 0.5, "stream": True}]
    assert response.iter_content_calls == [256]
    assert response.chunks_read == 1
    assert response.closed


def test_main_returns_nonzero_if_no_host_is_provided(capsys) -> None:
    """The CLI should require an explicit host or IP."""

    assert main([]) != 0
    assert "Usage:" in capsys.readouterr().err
