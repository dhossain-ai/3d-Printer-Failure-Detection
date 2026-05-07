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
