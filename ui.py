"""Tkinter source selection UI for PrintSentinel."""

import tkinter as tk
from tkinter import messagebox, simpledialog

from sources import VideoSource, mobile_camera_source, sample_video_source, webcam_source


class SourceSelectionUI:
    """Simple Tkinter menu for choosing a video source."""

    def __init__(self) -> None:
        """Create the source selection window."""

        self._root = tk.Tk()
        self._root.title("PrintSentinel")
        self._root.geometry("420x260")
        self._root.resizable(False, False)
        self._selected_source: VideoSource | None = None

        self._build()

    def run(self) -> VideoSource | None:
        """Show the menu and return the selected source."""

        self._root.mainloop()
        return self._selected_source

    def _build(self) -> None:
        """Build the source selection controls."""

        title = tk.Label(
            self._root,
            text="PrintSentinel",
            font=("Arial", 18, "bold"),
        )
        title.pack(pady=(24, 6))

        subtitle = tk.Label(
            self._root,
            text="Choose input source",
            font=("Arial", 12),
        )
        subtitle.pack(pady=(0, 18))

        tk.Button(
            self._root,
            text="Sample video",
            width=26,
            command=self._select_sample_video,
        ).pack(pady=6)
        tk.Button(
            self._root,
            text="Webcam",
            width=26,
            command=self._select_webcam,
        ).pack(pady=6)
        tk.Button(
            self._root,
            text="Mobile camera URL",
            width=26,
            command=self._select_mobile_camera,
        ).pack(pady=6)

    def _select_sample_video(self) -> None:
        """Select the bundled sample video."""

        self._selected_source = sample_video_source()
        self._root.destroy()

    def _select_webcam(self) -> None:
        """Select the default webcam."""

        self._selected_source = webcam_source()
        self._root.destroy()

    def _select_mobile_camera(self) -> None:
        """Prompt for and select a mobile camera stream URL."""

        url = simpledialog.askstring(
            "Mobile Camera URL",
            "Enter mobile camera URL:\nExample: http://192.168.1.5:4747/video",
            parent=self._root,
        )
        if url:
            self._selected_source = mobile_camera_source(url)
            self._root.destroy()


def choose_source() -> VideoSource | None:
    """Open the source selection UI and return the user's choice."""

    return SourceSelectionUI().run()


def show_error(message: str) -> None:
    """Show a Tkinter error dialog."""

    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("PrintSentinel", message)
        root.destroy()
    except tk.TclError:
        print(f"PrintSentinel error: {message}")
