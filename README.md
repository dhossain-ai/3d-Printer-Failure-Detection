# PrintSentinel

PrintSentinel is a Python MVP for camera/video-based 3D print failure detection. It watches a sample video, webcam, or mobile camera stream, runs a YOLO model, and raises a clear local response when likely print failures are confirmed across multiple frames.

3D print failures can waste hours of machine time and material. PrintSentinel focuses on a practical first step: reliable local monitoring with clean code paths that can later connect to real printer control.

## Current Features

### Phase 1: Monitoring MVP

- Tkinter source selection for sample video, webcam, or mobile camera URL
- YOLO model loading from `models/model.pt`
- OpenCV detection loop with annotated video
- Failure labels for classes like `spaghetti`, `stringing`, and `zits`
- Consecutive-frame confirmation before fail status
- Graceful handling for missing files and bad sources
- Quit monitoring with `q`

### Phase 2: Local Failure Response

- Confirmed failure screenshots saved to `captures/`
- Confirmed failure events appended to `logs/events.csv`
- Cooldown to avoid repeated screenshots, logs, and actions
- Terminal warning for every triggered failure event
- Simulated printer `stop` or `pause` action through `actions.py`

### Phase 3: Project Polish

- Dedicated overlay drawing module for cleaner runtime status
- Shared utility helpers for safe timestamps, filenames, and cooldown logic
- More readable monitoring overlay with source, status, fail counter, latest label, and cooldown
- Lightweight pytest coverage for core logic that does not require a camera or model
- Stronger startup and runtime error messages

### Phase 4: Safe Printer Control Architecture

- `printer_controller.py` abstraction for printer actions
- Simulated backend by default for safe local demos
- Optional generic HTTP backend for stop/pause/health requests
- Environment variable overrides for backend, action, URL, endpoints, and timeout
- Controller failures are reported clearly without crashing monitoring
- Tests for controller selection, HTTP request routing, and failure fallback

### Phase 5: Demo Readiness And Evaluation

- Mocked orchestration tests for confirmed failure and cooldown behavior
- Session summary printed at shutdown and saved to `logs/session_*.json`
- Overlay and terminal startup visibility for source, printer backend, and action
- Optional HTTP auth token and extra header support
- Lightweight architecture notes and demo asset checklist in `docs/`

### Phase 6: Notification Framework

- Confirmed-failure notifications routed through `actions.py`
- Provider manager that isolates notification errors from monitoring and printer control
- Optional Windows desktop toast provider using `windows-toasts` when installed
- Optional Telegram bot alerts with text or screenshot photo messages
- Optional SMTP email alerts with text or screenshot attachments
- Local Tkinter notification settings window with save and test controls
- Environment flags for enabling notifications and Windows desktop alerts

## Folder Structure

```text
printer_fail_demo/
├── main.py
├── config.py
├── ui.py
├── detector.py
├── runner.py
├── annotator.py
├── actions.py
├── printer_controller.py
├── notifications/
│   ├── manager.py
│   ├── models.py
│   └── providers/
│       ├── base.py
│       ├── email.py
│       ├── telegram.py
│       └── windows_toast.py
├── session_summary.py
├── sources.py
├── utils.py
├── docs/
│   └── architecture.md
├── tests/
│   ├── test_actions.py
│   ├── test_notifications.py
│   ├── test_printer_controller.py
│   ├── test_runner.py
│   └── test_utils.py
├── models/
│   └── model.pt
├── assets/
│   └── demo.mp4
├── captures/
└── logs/
    └── events.csv
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Choose one source:

- `Sample video` uses `assets/demo.mp4`
- `Webcam` uses camera index `0`
- `Mobile camera URL` accepts a stream URL such as `http://192.168.1.5:4747/video`

When a failure is confirmed, PrintSentinel saves a screenshot, writes a CSV row, prints a warning, and runs the configured printer action. The default printer backend is simulated, so the app remains safe to run without hardware.

## Configuration

Runtime settings live in `config.py`.

```python
CONFIDENCE_THRESHOLD = 0.35
CONSECUTIVE_FAIL_FRAMES = 3
ALERT_COOLDOWN_SECONDS = 20
PRINTER_BACKEND = "simulated"
PRINTER_ACTION = "stop"
PRINTER_BASE_URL = ""
PRINTER_STOP_ENDPOINT = "/stop"
PRINTER_PAUSE_ENDPOINT = "/pause"
PRINTER_HEALTH_ENDPOINT = "/health"
PRINTER_REQUEST_TIMEOUT_SECONDS = 3
PRINTER_API_TOKEN = ""
PRINTER_AUTH_HEADER_NAME = "Authorization"
PRINTER_EXTRA_HEADERS_JSON = ""
NOTIFICATIONS_ENABLED = False
NOTIFICATION_TIMEOUT_SECONDS = 5.0
WINDOWS_NOTIFICATIONS_ENABLED = False
WINDOWS_NOTIFICATION_APP_NAME = "PrintSentinel"
TELEGRAM_NOTIFICATIONS_ENABLED = False
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
TELEGRAM_SEND_SCREENSHOT = True
EMAIL_NOTIFICATIONS_ENABLED = False
SMTP_HOST = ""
SMTP_PORT = 465
SMTP_SECURITY = "ssl"
SMTP_USERNAME = ""
SMTP_PASSWORD = ""
EMAIL_FROM = ""
EMAIL_TO = ""
EMAIL_SEND_SCREENSHOT = True
```

Use `PRINTER_ACTION = "pause"` to request a pause instead of a stop.

## Printer Backends

### Simulated Backend

The simulated backend is the default and only prints clear terminal messages. It is the recommended mode for demos, development, and testing without hardware.

```bash
export PRINTSENTINEL_PRINTER_BACKEND=simulated
export PRINTSENTINEL_PRINTER_ACTION=stop
python main.py
```

### HTTP Backend

The HTTP backend sends generic requests to configured endpoints:

- `GET PRINTER_HEALTH_ENDPOINT`
- `POST PRINTER_STOP_ENDPOINT`
- `POST PRINTER_PAUSE_ENDPOINT`

Example:

```bash
export PRINTSENTINEL_PRINTER_BACKEND=http
export PRINTSENTINEL_PRINTER_ACTION=stop
export PRINTSENTINEL_PRINTER_BASE_URL=http://192.168.1.50:8080
export PRINTSENTINEL_PRINTER_STOP_ENDPOINT=/stop
export PRINTSENTINEL_PRINTER_PAUSE_ENDPOINT=/pause
export PRINTSENTINEL_PRINTER_HEALTH_ENDPOINT=/health
export PRINTSENTINEL_PRINTER_REQUEST_TIMEOUT_SECONDS=3
python main.py
```

Unprefixed names such as `PRINTER_BACKEND` and `PRINTER_BASE_URL` are also supported. `PRINTSENTINEL_` variables take precedence.

If HTTP configuration is incomplete, PrintSentinel falls back to the simulated backend. If healthcheck or action requests fail, it prints a warning and continues monitoring safely.

Optional auth/header examples:

```bash
export PRINTSENTINEL_PRINTER_API_TOKEN="Bearer replace-with-token"
export PRINTSENTINEL_PRINTER_AUTH_HEADER_NAME=Authorization
export PRINTSENTINEL_PRINTER_EXTRA_HEADERS_JSON='{"X-Printer-Profile": "demo"}'
python main.py
```

The token is sent as the configured header value. Include prefixes such as `Bearer` in the token value if your endpoint expects them.

## Notifications

Notifications are disabled by default. When enabled, PrintSentinel sends alerts after a confirmed failure screenshot, CSV row, and terminal warning are created. Notification failures are logged as warnings and never block the configured printer stop or pause action.

Never commit bot tokens, SMTP passwords, chat IDs, or local notification settings. Use environment variables or a local `.env` workflow outside version control.

### Notification Settings UI

The source selection window includes a `Notification Settings` button. It opens a local Tkinter settings window for Windows, Telegram, and SMTP email notifications. The window can save settings and send a test notification through the currently enabled providers.

Local UI settings are saved to:

```text
config/local_notification_settings.json
```

This file is ignored by Git. For this local MVP, the file stores notification secrets in plaintext so the desktop UI can remain simple. Production deployments should use environment variables, a secret manager, or encrypted local storage instead.

Notification config precedence is:

1. Environment variables, including `PRINTSENTINEL_`-prefixed names.
2. `config/local_notification_settings.json`.
3. Defaults in `config.py`.

Enable Windows desktop notifications:

```powershell
pip install windows-toasts
$env:PRINTSENTINEL_NOTIFICATIONS_ENABLED="true"
$env:PRINTSENTINEL_WINDOWS_NOTIFICATIONS_ENABLED="true"
$env:PRINTSENTINEL_WINDOWS_NOTIFICATION_APP_NAME="PrintSentinel"
python main.py
```

On non-Windows systems, the Windows provider reports a safe skip. If `windows-toasts` is not installed on Windows, PrintSentinel reports a warning and keeps monitoring.

Enable Telegram notifications:

```bash
export PRINTSENTINEL_NOTIFICATIONS_ENABLED=true
export PRINTSENTINEL_TELEGRAM_NOTIFICATIONS_ENABLED=true
export PRINTSENTINEL_TELEGRAM_BOT_TOKEN="replace-with-bot-token"
export PRINTSENTINEL_TELEGRAM_CHAT_ID="replace-with-chat-id"
export PRINTSENTINEL_TELEGRAM_SEND_SCREENSHOT=true
export PRINTSENTINEL_NOTIFICATION_TIMEOUT_SECONDS=5
python main.py
```

Telegram text alerts use `sendMessage`. If `TELEGRAM_SEND_SCREENSHOT` is true and a screenshot exists, PrintSentinel sends the alert with `sendPhoto`.

Enable Gmail SMTP email notifications:

```bash
export PRINTSENTINEL_NOTIFICATIONS_ENABLED=true
export PRINTSENTINEL_EMAIL_NOTIFICATIONS_ENABLED=true
export PRINTSENTINEL_SMTP_HOST=smtp.gmail.com
export PRINTSENTINEL_SMTP_PORT=465
export PRINTSENTINEL_SMTP_SECURITY=ssl
export PRINTSENTINEL_SMTP_USERNAME="your-address@gmail.com"
export PRINTSENTINEL_SMTP_PASSWORD="replace-with-gmail-app-password"
export PRINTSENTINEL_EMAIL_FROM="your-address@gmail.com"
export PRINTSENTINEL_EMAIL_TO="first@example.com,second@example.com"
export PRINTSENTINEL_EMAIL_SEND_SCREENSHOT=true
export PRINTSENTINEL_NOTIFICATION_TIMEOUT_SECONDS=5
python main.py
```

For Gmail, use an app password rather than your normal account password. `SMTP_SECURITY=starttls` with port `587` is also supported.

## Session Summary

Each monitoring run prints a terminal summary at shutdown and writes a small JSON file to `logs/session_*.json`. The summary includes:

- source used
- printer backend/action
- start/end time and duration
- frames processed
- failure-like detection frames
- confirmed failure sequences
- actions triggered
- screenshots saved
- last printer action result

## Demo Workflow

1. Start the app with `python main.py`.
2. Choose `Sample video`.
3. Watch the overlay for source, status, fail frame counter, latest detection, and cooldown.
4. Press `q` to quit the monitoring window.
5. Check `captures/` for failure screenshots.
6. Check `logs/events.csv` for event rows.
7. Check `logs/session_*.json` for the run summary.

## Screenshots

Add portfolio screenshots here after running the app:

- Source selection menu
- Monitoring window in `STATUS: MONITORING`
- Confirmed failure window in `STATUS: FAIL DETECTED -> STOP PRINTER`
- Example `logs/events.csv` row
- Example terminal session summary

## Tests

```bash
pytest -q
```

The test suite covers safe filename generation, cooldown behavior, CSV row creation, event log writing, simulated action routing, controller selection, HTTP request routing, notification handling, confirmed failure orchestration, and cooldown suppression. Notification tests mock Telegram requests and SMTP sessions, so they do not make real network calls. The suite does not require a webcam, live OpenCV window, YOLO model execution, or real printer.

HTTP controller tests use mocked request sessions and do not require a real printer.

## Roadmap

- Add printer-specific adapter examples behind `printer_controller.py`
- Add calibration guidance for custom models and camera placement
- Add optional UI controls for cooldown and simulated action mode
- Add richer screenshot examples for GitHub documentation
- Add packaged sample logs/screenshots for portfolio demos
