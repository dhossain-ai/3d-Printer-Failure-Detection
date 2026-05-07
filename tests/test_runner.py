"""Tests for runner orchestration without live camera/model execution."""

from pathlib import Path
from typing import Any

from actions import FailureEvent
from creality_status import CrealityPrinterStatus
from detector import FrameDetection
from runner import PrintSentinelRunner
from sources import SourceKind, VideoSource


class FakeCapture:
    """Small cv2.VideoCapture stand-in for runner tests."""

    def __init__(self, frame_count: int) -> None:
        """Create a fake capture with a fixed number of frames."""

        self._remaining_frames = frame_count
        self.released = False

    def read(self) -> tuple[bool, object | None]:
        """Return frames until exhausted."""

        if self._remaining_frames <= 0:
            return False, None

        self._remaining_frames -= 1
        return True, object()

    def release(self) -> None:
        """Record release."""

        self.released = True


class FakeDetector:
    """Detector that returns a configured failure sequence."""

    def __init__(self, failures: list[bool]) -> None:
        """Create a fake detector from per-frame failure values."""

        self._failures = failures
        self.calls = 0

    def detect(self, frame: Any) -> FrameDetection:
        """Return the next fake detection."""

        failure_detected = self._failures[self.calls]
        self.calls += 1
        return FrameDetection(
            annotated_frame=frame,
            failure_detected=failure_detected,
            label="spaghetti" if failure_detected else None,
            confidence=0.9 if failure_detected else 0.0,
        )


class FakeCv2:
    """Minimal OpenCV UI stand-in."""

    def imshow(self, window_name: str, frame: Any) -> None:
        """Ignore imshow calls."""

    def waitKey(self, delay: int) -> int:
        """Never request quit."""

        return -1

    def destroyAllWindows(self) -> None:
        """Ignore destroy calls."""


class FakeStatusPoller:
    """Small status poller stand-in."""

    instances: list["FakeStatusPoller"] = []

    def __init__(
        self,
        ws_url: str,
        poll_seconds: float,
        timeout_seconds: float,
    ) -> None:
        """Record poller construction."""

        self.ws_url = ws_url
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.started = False
        self.stopped = False
        self.latest_status = CrealityPrinterStatus(
            connected=True,
            hostname="K1C-CREALITY1",
            model="K1C",
        )
        self.instances.append(self)

    def start(self) -> None:
        """Record start."""

        self.started = True

    def stop(self) -> None:
        """Record stop."""

        self.stopped = True


def test_runner_triggers_actions_once_after_confirmation(monkeypatch, tmp_path: Path) -> None:
    """Runner should trigger failure actions after consecutive confirmation."""

    detector = FakeDetector([True, True, True, True])
    runner = PrintSentinelRunner(
        detector=detector,  # type: ignore[arg-type]
        consecutive_fail_frames=3,
        alert_cooldown_seconds=999,
    )
    capture = FakeCapture(frame_count=4)
    events: list[tuple[str, str, float]] = []

    monkeypatch.setattr("runner.open_capture", lambda source: (capture, None))
    monkeypatch.setattr("runner.draw_monitoring_overlay", lambda frame, state: frame)
    monkeypatch.setattr("runner._cv2", lambda: FakeCv2())
    monkeypatch.setattr("runner.print_session_start", lambda summary: None)
    monkeypatch.setattr("runner.print_session_summary", lambda summary, path: None)
    monkeypatch.setattr(
        "runner.SessionSummary.write_json",
        lambda self: tmp_path / "session.json",
    )

    def fake_handle(
        frame: Any,
        source: str,
        label: str,
        confidence: float,
    ) -> FailureEvent:
        events.append((source, label, confidence))
        return FailureEvent(
            timestamp="2026-04-29T12:30:01+03:00",
            source=source,
            label=label,
            confidence=confidence,
            action="stop",
            screenshot_path=tmp_path / "failure.jpg",
            action_success=True,
            action_message="ok",
        )

    monkeypatch.setattr("runner.handle_confirmed_failure", fake_handle)

    error = runner.run(
        VideoSource(
            kind=SourceKind.SAMPLE_VIDEO,
            label="Sample video",
            value="demo.mp4",
        )
    )

    assert error is None
    assert capture.released
    assert events == [("Sample video", "spaghetti", 0.9)]


def test_runner_cooldown_suppresses_repeated_actions(monkeypatch, tmp_path: Path) -> None:
    """Runner should keep monitoring but suppress action spam during cooldown."""

    detector = FakeDetector([True, True, True, True, True])
    runner = PrintSentinelRunner(
        detector=detector,  # type: ignore[arg-type]
        consecutive_fail_frames=2,
        alert_cooldown_seconds=999,
    )
    action_count = 0

    monkeypatch.setattr("runner.open_capture", lambda source: (FakeCapture(5), None))
    monkeypatch.setattr("runner.draw_monitoring_overlay", lambda frame, state: frame)
    monkeypatch.setattr("runner._cv2", lambda: FakeCv2())
    monkeypatch.setattr("runner.print_session_start", lambda summary: None)
    monkeypatch.setattr("runner.print_session_summary", lambda summary, path: None)
    monkeypatch.setattr(
        "runner.SessionSummary.write_json",
        lambda self: tmp_path / "session.json",
    )

    def fake_handle(
        frame: Any,
        source: str,
        label: str,
        confidence: float,
    ) -> FailureEvent:
        nonlocal action_count
        action_count += 1
        return FailureEvent(
            timestamp="2026-04-29T12:30:01+03:00",
            source=source,
            label=label,
            confidence=confidence,
            action="stop",
            screenshot_path=tmp_path / "failure.jpg",
            action_success=True,
            action_message="ok",
        )

    monkeypatch.setattr("runner.handle_confirmed_failure", fake_handle)

    runner.run(VideoSource(kind=SourceKind.WEBCAM, label="Webcam 0", value=0))

    assert action_count == 1


def test_runner_starts_and_stops_status_poller_when_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Runner should manage the read-only status poller lifecycle."""

    FakeStatusPoller.instances = []
    captured_states: list[Any] = []

    monkeypatch.setattr("runner.CREALITY_STATUS_ENABLED", True)
    monkeypatch.setattr("runner.CREALITY_WS_URL", "ws://printer:9999")
    monkeypatch.setattr("runner.CREALITY_STATUS_POLL_SECONDS", 3.0)
    monkeypatch.setattr("runner.CREALITY_STATUS_TIMEOUT_SECONDS", 1.5)
    monkeypatch.setattr("runner.CrealityStatusPoller", FakeStatusPoller)
    monkeypatch.setattr("runner.open_capture", lambda source: (FakeCapture(1), None))
    monkeypatch.setattr("runner._cv2", lambda: FakeCv2())
    monkeypatch.setattr("runner.print_session_start", lambda summary: None)
    monkeypatch.setattr("runner.print_session_summary", lambda summary, path: None)
    monkeypatch.setattr(
        "runner.SessionSummary.write_json",
        lambda self: tmp_path / "session.json",
    )

    def fake_draw(frame: Any, state: Any) -> Any:
        captured_states.append(state)
        return frame

    monkeypatch.setattr("runner.draw_monitoring_overlay", fake_draw)

    runner = PrintSentinelRunner(
        detector=FakeDetector([False]),  # type: ignore[arg-type]
    )
    runner.run(VideoSource(kind=SourceKind.WEBCAM, label="Webcam 0", value=0))

    assert len(FakeStatusPoller.instances) == 1
    poller = FakeStatusPoller.instances[0]
    assert poller.ws_url == "ws://printer:9999"
    assert poller.poll_seconds == 3.0
    assert poller.timeout_seconds == 1.5
    assert poller.started
    assert poller.stopped
    assert captured_states[0].creality_status == poller.latest_status


def test_runner_does_not_start_status_poller_without_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Status polling should stay disabled unless enabled and configured."""

    FakeStatusPoller.instances = []

    monkeypatch.setattr("runner.CREALITY_STATUS_ENABLED", True)
    monkeypatch.setattr("runner.CREALITY_WS_URL", "")
    monkeypatch.setattr("runner.CrealityStatusPoller", FakeStatusPoller)
    monkeypatch.setattr("runner.open_capture", lambda source: (FakeCapture(1), None))
    monkeypatch.setattr("runner.draw_monitoring_overlay", lambda frame, state: frame)
    monkeypatch.setattr("runner._cv2", lambda: FakeCv2())
    monkeypatch.setattr("runner.print_session_start", lambda summary: None)
    monkeypatch.setattr("runner.print_session_summary", lambda summary, path: None)
    monkeypatch.setattr(
        "runner.SessionSummary.write_json",
        lambda self: tmp_path / "session.json",
    )

    runner = PrintSentinelRunner(
        detector=FakeDetector([False]),  # type: ignore[arg-type]
    )
    runner.run(VideoSource(kind=SourceKind.WEBCAM, label="Webcam 0", value=0))

    assert FakeStatusPoller.instances == []
