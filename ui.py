"""Tkinter source selection UI for PrintSentinel."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config import PRINTER_CAMERA_TYPE, PRINTER_CAMERA_URL
from notifications.settings import (
    LOCAL_NOTIFICATION_SETTINGS_PATH,
    load_notification_settings,
    save_notification_settings,
    send_test_notification,
    validate_notification_settings,
)
from sources import (
    VideoSource,
    mobile_camera_source,
    printer_camera_source,
    sample_video_source,
    webcam_source,
)


class SourceSelectionUI:
    """Simple Tkinter menu for choosing a video source."""

    def __init__(self) -> None:
        """Create the source selection window."""

        self._root = tk.Tk()
        self._root.title("PrintSentinel")
        self._root.geometry("420x355")
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
        tk.Button(
            self._root,
            text="Printer camera",
            width=26,
            command=self._select_printer_camera,
        ).pack(pady=6)
        tk.Button(
            self._root,
            text="Notification Settings",
            width=26,
            command=self._open_notification_settings,
        ).pack(pady=(14, 6))

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

    def _select_printer_camera(self) -> None:
        """Select the configured printer camera or prompt for its URL."""

        url = PRINTER_CAMERA_URL
        if not url:
            url = simpledialog.askstring(
                "Printer Camera URL",
                (
                    "Enter printer camera URL:\n"
                    "Example: http://<printer-ip>:8080/?action=stream"
                ),
                parent=self._root,
            )

        if url:
            self._selected_source = printer_camera_source(url, PRINTER_CAMERA_TYPE)
            self._root.destroy()

    def _open_notification_settings(self) -> None:
        """Open local notification settings without changing source selection."""

        NotificationSettingsWindow(self._root)


class NotificationSettingsWindow:
    """Tkinter editor for local notification settings."""

    def __init__(self, parent: tk.Tk) -> None:
        """Create the notification settings window."""

        self._window = tk.Toplevel(parent)
        self._window.title("Notification Settings")
        self._window.geometry("620x720")
        self._window.resizable(False, True)
        self._settings = load_notification_settings()
        self._vars: dict[str, tk.BooleanVar | tk.StringVar] = {}
        self._result_text: tk.Text | None = None

        self._build()

    def _build(self) -> None:
        """Build notification settings controls."""

        frame = tk.Frame(self._window, padx=18, pady=14)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Notification Settings",
            font=("Arial", 15, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        row = 1
        row = self._add_checkbox(frame, row, "NOTIFICATIONS_ENABLED", "Enable notifications")
        row = self._add_checkbox(
            frame,
            row,
            "WINDOWS_NOTIFICATIONS_ENABLED",
            "Enable Windows desktop notifications",
        )
        row = self._add_separator(frame, row)
        row = self._add_checkbox(
            frame,
            row,
            "TELEGRAM_NOTIFICATIONS_ENABLED",
            "Enable Telegram notifications",
        )
        row = self._add_entry(frame, row, "TELEGRAM_BOT_TOKEN", "Telegram bot token", masked=True)
        row = self._add_entry(frame, row, "TELEGRAM_CHAT_ID", "Telegram chat ID")
        row = self._add_checkbox(
            frame,
            row,
            "TELEGRAM_SEND_SCREENSHOT",
            "Send Telegram screenshot",
        )
        row = self._add_separator(frame, row)
        row = self._add_checkbox(
            frame,
            row,
            "EMAIL_NOTIFICATIONS_ENABLED",
            "Enable email notifications",
        )
        row = self._add_entry(frame, row, "SMTP_HOST", "SMTP host")
        row = self._add_entry(frame, row, "SMTP_PORT", "SMTP port")
        row = self._add_dropdown(
            frame,
            row,
            "SMTP_SECURITY",
            "SMTP security",
            ("ssl", "starttls", "none"),
        )
        row = self._add_entry(frame, row, "SMTP_USERNAME", "SMTP username")
        row = self._add_entry(frame, row, "SMTP_PASSWORD", "SMTP password", masked=True)
        row = self._add_entry(frame, row, "EMAIL_FROM", "From email")
        row = self._add_entry(frame, row, "EMAIL_TO", "Recipient emails")
        row = self._add_checkbox(
            frame,
            row,
            "EMAIL_SEND_SCREENSHOT",
            "Send email screenshot",
        )
        row = self._add_entry(
            frame,
            row,
            "NOTIFICATION_MAX_SCREENSHOT_MB",
            "Max screenshot MB",
        )
        row = self._add_separator(frame, row)

        button_frame = tk.Frame(frame)
        button_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 10))
        tk.Button(button_frame, text="Save", width=14, command=self._save).pack(side="left")
        tk.Button(
            button_frame,
            text="Test Notification",
            width=18,
            command=self._test_notification,
        ).pack(side="left", padx=(8, 0))

        row += 1
        tk.Label(frame, text="Results").grid(row=row, column=0, sticky="nw")
        self._result_text = tk.Text(frame, width=54, height=7, wrap="word")
        self._result_text.grid(row=row, column=1, sticky="w")
        self._set_results(
            f"Local settings file: {LOCAL_NOTIFICATION_SETTINGS_PATH}"
        )

    def _add_checkbox(
        self,
        frame: tk.Frame,
        row: int,
        key: str,
        label: str,
    ) -> int:
        """Add a checkbox row."""

        variable = tk.BooleanVar(value=bool(self._settings.get(key, False)))
        self._vars[key] = variable
        tk.Checkbutton(frame, text=label, variable=variable).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=3,
        )
        return row + 1

    def _add_entry(
        self,
        frame: tk.Frame,
        row: int,
        key: str,
        label: str,
        masked: bool = False,
    ) -> int:
        """Add a labeled text entry row."""

        variable = tk.StringVar(value=str(self._settings.get(key, "")))
        self._vars[key] = variable
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
        tk.Entry(frame, textvariable=variable, width=42, show="*" if masked else "").grid(
            row=row,
            column=1,
            sticky="w",
            pady=3,
        )
        return row + 1

    def _add_dropdown(
        self,
        frame: tk.Frame,
        row: int,
        key: str,
        label: str,
        values: tuple[str, ...],
    ) -> int:
        """Add a labeled dropdown row."""

        variable = tk.StringVar(value=str(self._settings.get(key, values[0])))
        self._vars[key] = variable
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
        dropdown = ttk.Combobox(
            frame,
            textvariable=variable,
            values=values,
            width=39,
            state="readonly",
        )
        dropdown.grid(row=row, column=1, sticky="w", pady=3)
        return row + 1

    def _add_separator(self, frame: tk.Frame, row: int) -> int:
        """Add a visual separator row."""

        ttk.Separator(frame, orient="horizontal").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=8,
        )
        return row + 1

    def _collect_settings(self) -> dict[str, object]:
        """Collect current UI values into a settings dictionary."""

        return {key: variable.get() for key, variable in self._vars.items()}

    def _save(self) -> None:
        """Validate and save local notification settings."""

        settings = self._collect_settings()
        errors = validate_notification_settings(settings)
        if errors:
            messagebox.showerror("Notification Settings", "\n".join(errors))
            self._set_results("\n".join(errors))
            return

        try:
            save_notification_settings(settings)
        except OSError as exc:
            messagebox.showerror("Notification Settings", f"Settings were not saved: {exc}")
            self._set_results(f"Settings were not saved: {exc}")
            return
        except ValueError as exc:
            messagebox.showerror("Notification Settings", str(exc))
            self._set_results(str(exc))
            return

        messagebox.showinfo("Notification Settings", "Settings saved.")
        self._set_results(f"Settings saved to {LOCAL_NOTIFICATION_SETTINGS_PATH}")

    def _test_notification(self) -> None:
        """Send a test notification and display provider results."""

        try:
            results = send_test_notification(self._collect_settings())
        except Exception as exc:  # noqa: BLE001 - UI should not crash on provider failures.
            self._set_results(f"Test notification failed: {exc}")
            return

        if not results:
            self._set_results("No notification providers are enabled.")
            return

        self._set_results(
            "\n".join(
                (
                    f"{result.provider}/{result.destination_id}: "
                    f"{'success' if result.success else 'failed'} - {result.message}"
                )
                for result in results
            )
        )

    def _set_results(self, message: str) -> None:
        """Replace result text in the settings window."""

        if self._result_text is None:
            return

        self._result_text.delete("1.0", tk.END)
        self._result_text.insert(tk.END, message)


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
