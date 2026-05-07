"""Tests for monitoring overlay drawing."""

from typing import Any

import numpy as np

from annotator import OverlayState, draw_monitoring_overlay
from creality_status import CrealityPrinterStatus


class FakeCv2:
    """Minimal OpenCV drawing stand-in."""

    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 16

    def __init__(self) -> None:
        """Create an empty recorder."""

        self.texts: list[str] = []

    def rectangle(self, *args: Any, **kwargs: Any) -> None:
        """Ignore rectangle calls."""

    def putText(
        self,
        frame: Any,
        text: str,
        origin: tuple[int, int],
        font: int,
        scale: float,
        color: tuple[int, int, int],
        thickness: int,
        line_type: int,
    ) -> None:
        """Record drawn text."""

        self.texts.append(text)


def test_overlay_renders_creality_status_text(monkeypatch) -> None:
    """Overlay should draw concise live printer status when present."""

    fake_cv2 = FakeCv2()
    monkeypatch.setattr("annotator._cv2", lambda: fake_cv2)
    frame = np.zeros((240, 640, 3), dtype=np.uint8)

    draw_monitoring_overlay(
        frame,
        OverlayState(
            source_name="Printer camera",
            confirmed_failure=False,
            fail_frame_count=0,
            creality_status=CrealityPrinterStatus(
                connected=True,
                hostname="K1C-CREALITY1",
                model="K1C",
                state="printing",
                device_state="1",
                nozzle_temp=25.11,
                target_nozzle_temp=0.0,
                bed_temp=23.19,
                target_bed_temp=0.0,
                print_progress=12.5,
                light_on=True,
            ),
        ),
    )

    assert any("Printer status: K1C/K1C-CREALITY1" in text for text in fake_cv2.texts)
    assert any("N 25.1/0.0C" in text for text in fake_cv2.texts)
    assert any("B 23.2/0.0C" in text for text in fake_cv2.texts)
    assert any("12.5%" in text for text in fake_cv2.texts)
    assert any("Light on" in text for text in fake_cv2.texts)
