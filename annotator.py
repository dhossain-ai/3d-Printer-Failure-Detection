"""Frame overlay drawing for PrintSentinel monitoring."""

from dataclasses import dataclass
from typing import Any

from config import (
    COLOR_OVERLAY_BACKGROUND,
    COLOR_STATUS_CHECKING,
    COLOR_STATUS_DETAIL,
    COLOR_STATUS_FAIL,
    COLOR_STATUS_OK,
    COLOR_STATUS_TEXT,
    CONSECUTIVE_FAIL_FRAMES,
    OVERLAY_FONT_SCALE,
    OVERLAY_HEIGHT,
    OVERLAY_LINE_HEIGHT,
    OVERLAY_PADDING,
    OVERLAY_THICKNESS,
    OVERLAY_TITLE_FONT_SCALE,
    OVERLAY_TITLE_THICKNESS,
    STATUS_CONFIRMING,
    STATUS_FAIL_DETECTED,
    STATUS_MONITORING,
)
from creality_status import CrealityPrinterStatus


@dataclass(frozen=True)
class OverlayState:
    """Current monitoring state to draw over a frame."""

    source_name: str
    confirmed_failure: bool
    fail_frame_count: int
    fail_frame_threshold: int = CONSECUTIVE_FAIL_FRAMES
    label: str | None = None
    confidence: float = 0.0
    cooldown_remaining_seconds: int = 0
    printer_backend: str = "simulated"
    printer_action: str = "stop"
    last_action_result: str | None = None
    creality_status: CrealityPrinterStatus | None = None


def draw_monitoring_overlay(frame: Any, state: OverlayState) -> Any:
    """Draw a compact monitoring overlay on an annotated frame."""

    cv2 = _cv2()
    status_text = _status_text(state)
    status_color = _status_color(state)
    last_detection = _last_detection_text(state)
    cooldown_text = _cooldown_text(state)
    printer_text = f"Printer: {state.printer_backend}/{state.printer_action}"
    action_text = _action_result_text(state)
    status_left, status_right = _creality_status_text(state.creality_status)

    cv2.rectangle(
        frame,
        (0, 0),
        (frame.shape[1], OVERLAY_HEIGHT),
        COLOR_OVERLAY_BACKGROUND,
        thickness=-1,
    )
    cv2.rectangle(
        frame,
        (0, 0),
        (8, OVERLAY_HEIGHT),
        status_color,
        thickness=-1,
    )

    left_x = OVERLAY_PADDING
    right_x = max(left_x, frame.shape[1] // 2)
    y = OVERLAY_PADDING + 8

    _put_text(
        frame,
        status_text,
        (left_x, y),
        scale=OVERLAY_TITLE_FONT_SCALE,
        color=COLOR_STATUS_TEXT,
        thickness=OVERLAY_TITLE_THICKNESS,
    )
    _put_text(
        frame,
        f"Source: {state.source_name}",
        (right_x, y),
        color=COLOR_STATUS_DETAIL,
    )

    y += OVERLAY_LINE_HEIGHT
    _put_text(
        frame,
        f"Fail frames: {state.fail_frame_count}/{state.fail_frame_threshold}",
        (left_x, y),
        color=COLOR_STATUS_DETAIL,
    )
    _put_text(
        frame,
        last_detection,
        (right_x, y),
        color=COLOR_STATUS_DETAIL,
    )

    y += OVERLAY_LINE_HEIGHT
    _put_text(
        frame,
        cooldown_text,
        (left_x, y),
        color=COLOR_STATUS_DETAIL,
    )
    _put_text(
        frame,
        printer_text,
        (right_x, y),
        color=COLOR_STATUS_DETAIL,
    )

    y += OVERLAY_LINE_HEIGHT
    _put_text(
        frame,
        action_text,
        (left_x, y),
        color=COLOR_STATUS_DETAIL,
    )
    _put_text(
        frame,
        "Press q to quit",
        (right_x, y),
        color=COLOR_STATUS_DETAIL,
    )

    if status_left is not None:
        y += OVERLAY_LINE_HEIGHT
        _put_text(
            frame,
            status_left,
            (left_x, y),
            color=COLOR_STATUS_DETAIL,
        )
        if status_right is not None:
            _put_text(
                frame,
                status_right,
                (right_x, y),
                color=COLOR_STATUS_DETAIL,
            )

    return frame


def _status_text(state: OverlayState) -> str:
    """Return the user-facing status line."""

    if state.confirmed_failure:
        return STATUS_FAIL_DETECTED

    if state.fail_frame_count > 0:
        return STATUS_CONFIRMING

    return STATUS_MONITORING


def _status_color(state: OverlayState) -> tuple[int, int, int]:
    """Return the status accent color."""

    if state.confirmed_failure:
        return COLOR_STATUS_FAIL

    if state.fail_frame_count > 0:
        return COLOR_STATUS_CHECKING

    return COLOR_STATUS_OK


def _last_detection_text(state: OverlayState) -> str:
    """Return compact text describing the latest failure-like detection."""

    if state.label is None:
        return "Last detection: none"

    return f"Last detection: {state.label} ({state.confidence:.2f})"


def _cooldown_text(state: OverlayState) -> str:
    """Return cooldown text for the overlay."""

    if state.cooldown_remaining_seconds > 0:
        return f"Cooldown: {state.cooldown_remaining_seconds}s"

    return "Cooldown: ready"


def _action_result_text(state: OverlayState) -> str:
    """Return compact text for the latest printer action result."""

    if state.last_action_result is None:
        return "Last action: none"

    return f"Last action: {state.last_action_result}"


def _creality_status_text(
    status: CrealityPrinterStatus | None,
) -> tuple[str | None, str | None]:
    """Return compact Creality status overlay text."""

    if status is None:
        return None, None

    if not status.connected or status.error is not None:
        return "Printer status: unavailable", None

    identity = _join_status_parts(status.model, status.hostname)
    state = _join_status_parts(status.state, status.device_state)
    left = "Printer status"
    if identity:
        left += f": {identity}"
    if state:
        left += f" [{state}]"

    temp_parts = [
        _temp_text("N", status.nozzle_temp, status.target_nozzle_temp),
        _temp_text("B", status.bed_temp, status.target_bed_temp),
    ]
    right_parts = [part for part in temp_parts if part]
    if status.print_progress is not None and status.print_progress > 0:
        right_parts.append(f"{status.print_progress:.1f}%")
    if status.light_on is not None:
        right_parts.append(f"Light {'on' if status.light_on else 'off'}")

    return left, " | ".join(right_parts) if right_parts else None


def _join_status_parts(*values: str | None) -> str:
    """Join present status values."""

    return "/".join(value for value in values if value)


def _temp_text(label: str, current: float | None, target: float | None) -> str | None:
    """Return compact temperature text."""

    if current is None and target is None:
        return None
    current_text = "-" if current is None else f"{current:.1f}"
    target_text = "-" if target is None else f"{target:.1f}"
    return f"{label} {current_text}/{target_text}C"


def _put_text(
    frame: Any,
    text: str,
    origin: tuple[int, int],
    scale: float = OVERLAY_FONT_SCALE,
    color: tuple[int, int, int] = COLOR_STATUS_TEXT,
    thickness: int = OVERLAY_THICKNESS,
) -> None:
    """Draw anti-aliased OpenCV text."""

    cv2 = _cv2()
    cv2.putText(
        frame,
        text,
        origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def _cv2() -> Any:
    """Import OpenCV only when frame drawing is actually needed."""

    import cv2

    return cv2
