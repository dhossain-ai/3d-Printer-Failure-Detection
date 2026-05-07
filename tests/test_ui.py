"""Tests for UI behavior that does not require a display."""

from sources import SourceKind
from ui import SourceSelectionUI


class FakeRoot:
    """Small root stand-in for source selection tests."""

    def __init__(self) -> None:
        """Create a fake root."""

        self.destroyed = False

    def destroy(self) -> None:
        """Record window destruction."""

        self.destroyed = True


def test_source_selection_sample_video_behavior_is_unchanged() -> None:
    """Sample video selection should still select and close the root."""

    ui = SourceSelectionUI.__new__(SourceSelectionUI)
    ui._root = FakeRoot()
    ui._selected_source = None

    ui._select_sample_video()

    assert ui._selected_source is not None
    assert ui._selected_source.kind == SourceKind.SAMPLE_VIDEO
    assert ui._root.destroyed


def test_notification_settings_button_keeps_source_unselected(monkeypatch) -> None:
    """Opening settings should not select or close a video source."""

    opened_with: list[object] = []

    class FakeNotificationSettingsWindow:
        """Settings window stand-in."""

        def __init__(self, parent) -> None:
            """Record the parent window."""

            opened_with.append(parent)

    ui = SourceSelectionUI.__new__(SourceSelectionUI)
    ui._root = FakeRoot()
    ui._selected_source = None

    monkeypatch.setattr("ui.NotificationSettingsWindow", FakeNotificationSettingsWindow)

    ui._open_notification_settings()

    assert opened_with == [ui._root]
    assert ui._selected_source is None
    assert not ui._root.destroyed


def test_source_selection_includes_printer_camera_option(monkeypatch) -> None:
    """Source selection controls should include a printer camera button."""

    created_buttons: list[str] = []

    class FakeWidget:
        """Widget stand-in with pack support."""

        def __init__(self, *args, **kwargs) -> None:
            """Ignore widget arguments."""

        def pack(self, *args, **kwargs) -> None:
            """Ignore pack calls."""

    class FakeButton(FakeWidget):
        """Button stand-in that records labels."""

        def __init__(self, *args, **kwargs) -> None:
            """Record the button text."""

            created_buttons.append(kwargs["text"])

    ui = SourceSelectionUI.__new__(SourceSelectionUI)
    ui._root = FakeRoot()

    monkeypatch.setattr("ui.tk.Label", FakeWidget)
    monkeypatch.setattr("ui.tk.Button", FakeButton)

    ui._build()

    assert "Printer camera" in created_buttons


def test_select_printer_camera_uses_configured_url(monkeypatch) -> None:
    """Configured printer camera URL should be selected without prompting."""

    ui = SourceSelectionUI.__new__(SourceSelectionUI)
    ui._root = FakeRoot()
    ui._selected_source = None

    monkeypatch.setattr("ui.PRINTER_CAMERA_URL", "http://printer:8080/?action=stream")
    monkeypatch.setattr("ui.PRINTER_CAMERA_TYPE", "stream")

    ui._select_printer_camera()

    assert ui._selected_source is not None
    assert ui._selected_source.kind == SourceKind.PRINTER_CAMERA
    assert ui._selected_source.value == "http://printer:8080/?action=stream"
    assert ui._root.destroyed


def test_select_printer_camera_prompts_when_url_is_empty(monkeypatch) -> None:
    """Empty printer camera config should prompt for a URL."""

    prompts: list[str] = []

    def fake_askstring(title: str, prompt: str, parent) -> str:
        prompts.append(prompt)
        return "http://printer:8080/?action=stream"

    ui = SourceSelectionUI.__new__(SourceSelectionUI)
    ui._root = FakeRoot()
    ui._selected_source = None

    monkeypatch.setattr("ui.PRINTER_CAMERA_URL", "")
    monkeypatch.setattr("ui.PRINTER_CAMERA_TYPE", "stream")
    monkeypatch.setattr("ui.simpledialog.askstring", fake_askstring)

    ui._select_printer_camera()

    assert "http://<printer-ip>:8080/?action=stream" in prompts[0]
    assert ui._selected_source is not None
    assert ui._selected_source.kind == SourceKind.PRINTER_CAMERA
    assert ui._selected_source.value == "http://printer:8080/?action=stream"
    assert ui._root.destroyed
