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
├── creality_status.py
├── creality_status_poller.py
├── printer_controller.py
├── notifications/
│   ├── dispatcher.py
│   ├── logging.py
│   ├── manager.py
│   ├── models.py
│   ├── screenshots.py
│   ├── settings.py
│   └── providers/
│       ├── base.py
│       ├── email.py
│       ├── telegram.py
│       └── windows_toast.py
├── session_summary.py
├── sources.py
├── utils.py
├── tools/
│   ├── discover_printer.py
│   ├── inspect_printer_websocket.py
│   ├── inspect_printer_webui.py
│   ├── scan_creality_js_commands.py
│   └── read_creality_status.py
├── docs/
│   ├── architecture.md
│   ├── creality_command_capture_template.md
│   └── creality_command_discovery.md
├── tests/
│   ├── test_actions.py
│   ├── test_config.py
│   ├── test_creality_status.py
│   ├── test_creality_status_poller.py
│   ├── test_detector.py
│   ├── test_discover_printer.py
│   ├── test_inspect_printer_webui.py
│   ├── test_inspect_printer_websocket.py
│   ├── test_notifications.py
│   ├── test_printer_controller.py
│   ├── test_read_creality_status.py
│   ├── test_runner.py
│   ├── test_session_summary.py
│   ├── test_sources.py
│   ├── test_scan_creality_js_commands.py
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
MODEL_DEVICE = "auto"
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
PRINTER_CAMERA_URL = ""
PRINTER_CAMERA_TYPE = "stream"
CREALITY_WS_URL = ""
CREALITY_STATUS_TIMEOUT_SECONDS = 5.0
CREALITY_STATUS_ENABLED = False
CREALITY_STATUS_POLL_SECONDS = 5.0
NOTIFICATIONS_ENABLED = False
NOTIFICATION_TIMEOUT_SECONDS = 5.0
NOTIFICATION_MAX_SCREENSHOT_MB = 5.0
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

## Model Device / GPU Troubleshooting

Model inference device selection is explicit through `PRINTSENTINEL_MODEL_DEVICE`:

```bash
export PRINTSENTINEL_MODEL_DEVICE=auto
python main.py
```

`auto` is the default and lets Ultralytics choose the device. To force CPU inference:

```bash
export PRINTSENTINEL_MODEL_DEVICE=cpu
python main.py
```

To request GPU inference:

```bash
export PRINTSENTINEL_MODEL_DEVICE=cuda
python main.py
```

`PRINTSENTINEL_MODEL_DEVICE=0` is also supported for GPU device `0`.

If prediction fails with an error mentioning `torchvision::nms`, the CUDA backend, or an invalid device id, your local `torch` and `torchvision` builds may not match the installed CUDA runtime. Set `PRINTSENTINEL_MODEL_DEVICE=cpu` to keep monitoring on CPU, or install matching CUDA builds of both `torch` and `torchvision` before using GPU inference.

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

## Real Printer Discovery

Use the standalone discovery utility to identify which read-only LAN endpoints are available before enabling any real camera or printer-control integration.

```bash
python tools/discover_printer.py 192.168.12.236
```

The utility only sends HTTP `GET` probes and does not pause, stop, move, heat, extrude, or send G-code. Stream endpoints are opened with short timeouts, only a tiny initial sample is read, and the response is closed immediately.

Useful results include:

- `moonraker_api`: a Moonraker API endpoint responded on port `7125`
- `camera_stream`: an MJPEG camera stream endpoint was found
- `camera_snapshot`: a still-image camera endpoint was found

The printer IP can change if your router DHCP lease changes. Check the printer screen or reserve the IP in your router before relying on the same address later.

## Printer Web UI Inspection

When Moonraker port `7125` is unavailable but the printer web UI responds on port `80`, use the standalone inspector to look for statically visible UI assets and endpoint-looking strings:

```bash
python tools/inspect_printer_webui.py 192.168.137.211
```

This utility is read-only. It fetches `http://<host>/` with `GET`, optionally fetches a small number of same-origin JavaScript files with `GET`, caps bytes read per file, and never calls discovered API or control-looking endpoints.

The report lists discovered scripts, stylesheets, possible read-only endpoints, websocket candidates, and possible control endpoints marked `candidate only - not called`. These results help decide whether a future Creality-specific controller is possible without assuming Moonraker is present.

## Printer WebSocket Inspection

If the web UI exposes a WebSocket candidate such as `ws://<host>:9999`, use the standalone WebSocket inspector to connect briefly and listen for server-sent messages:

```bash
python tools/inspect_printer_websocket.py 192.168.137.211
```

This utility is read-only. It connects with short timeouts, listens for a few seconds, prints truncated message previews, and does not send application-level commands, G-code, or printer-control requests.

The results can show whether the WebSocket carries JSON status data and whether a future Creality-specific status or control integration might be possible. Do not run unknown commands discovered from JavaScript or WebSocket messages against the printer.

## Creality WebSocket Status

The Creality K1C web UI discovery found a status WebSocket feed at `ws://<printer-ip>:9999`. Use the read-only status CLI to connect, listen for JSON status messages, and print a stable summary:

```bash
python tools/read_creality_status.py ws://192.168.137.211:9999
```

This client does not send application-level commands, G-code, or printer-control requests. It is not wired into stop, pause, or any other printer action; the simulated printer backend remains the default.

Useful fields include hostname/model, state/device state, nozzle and bed temperatures with targets, box temperature, current print file, progress, time left, light status, and the raw keys seen in the message.

## Live Printer Status Overlay

PrintSentinel can display the latest read-only Creality WebSocket status in the monitoring overlay while detection continues. Enable it only after confirming the K1C WebSocket URL:

```powershell
$env:PRINTSENTINEL_CREALITY_WS_URL="ws://192.168.137.211:9999"
$env:PRINTSENTINEL_CREALITY_STATUS_ENABLED="true"
python main.py
```

The status poller runs in the background every `CREALITY_STATUS_POLL_SECONDS` seconds, defaulting to `5.0`, and stores only the latest snapshot in memory. If the printer status feed is unavailable, monitoring continues without blocking detection.

This overlay is read-only. It does not send WebSocket application commands, G-code, or printer-control requests, and it is not connected to stop, pause, or other printer actions.

## Creality Command Discovery

Real Creality printer control for failures is not fully implemented yet. Before adding any control adapter, use the static JavaScript scanner and manual browser capture workflow to understand the exact protocol used by the K1C web UI.

```bash
python tools/scan_creality_js_commands.py 192.168.137.211
```

The scanner is GET-only, fetches same-origin JavaScript assets, applies byte limits, and prints candidate snippets for WebSocket setup, possible command names, control payloads, file APIs, camera/video APIs, and status fields. It does not open a WebSocket or send any command payload.

For manual capture, follow [docs/creality_command_discovery.md](docs/creality_command_discovery.md) and use [docs/creality_command_capture_template.md](docs/creality_command_capture_template.md) for local notes. Do not test stop/cancel on an important print, do not run unknown commands against the printer, and do not paste tokens, secrets, or sensitive captures into committed files.

## Creality Low-Risk Controls

A safe WebSocket control client is available to send specific low-risk commands captured directly from the local K1C web UI. It is restricted to only these whitelisted commands and does not support arbitrary JSON sending.

Pause, stop, temperature, movement, extrude, retract, and arbitrary G-code are intentionally **not implemented** yet, as they require further safety review.

```bash
python tools/creality_control.py ws://192.168.137.211:9999 light on
python tools/creality_control.py ws://192.168.137.211:9999 light off
python tools/creality_control.py ws://192.168.137.211:9999 fan model on
python tools/creality_control.py ws://192.168.137.211:9999 fan auxiliary off
python tools/creality_control.py ws://192.168.137.211:9999 fan case on
python tools/creality_control.py ws://192.168.137.211:9999 files
```

Note: These CLI commands are safe to test manually, but the simulated printer backend remains the default for actual failure detection events. Real automated control must be opted into explicitly.

## Printer Camera Source

PrintSentinel can use a real printer camera as an input source without enabling printer-control commands. The Creality K1C discovery step found camera endpoints on port `8080`, with MJPEG stream and snapshot modes commonly exposed as:

- `http://<printer-ip>:8080/?action=stream`
- `http://<printer-ip>:8080/?action=snapshot`

Stream mode uses the normal OpenCV `VideoCapture` path and is the default:

```bash
export PRINTSENTINEL_PRINTER_CAMERA_URL="http://192.168.137.211:8080/?action=stream"
export PRINTSENTINEL_PRINTER_CAMERA_TYPE=stream
python main.py
```

Snapshot mode polls an image URL with HTTP timeouts and a modest polling interval:

```bash
export PRINTSENTINEL_PRINTER_CAMERA_URL="http://192.168.137.211:8080/?action=snapshot"
export PRINTSENTINEL_PRINTER_CAMERA_TYPE=snapshot
python main.py
```

On Windows PowerShell:

```powershell
$env:PRINTSENTINEL_PRINTER_CAMERA_URL="http://192.168.137.211:8080/?action=stream"
$env:PRINTSENTINEL_PRINTER_CAMERA_TYPE="stream"
python main.py
```

Then choose `Printer camera` in the source selection window. If `PRINTSENTINEL_PRINTER_CAMERA_URL` is not set, the UI prompts for a URL.

The printer IP can change when using hotspot or router DHCP. If the camera stops opening, check the printer screen or reserve the address in your router.

## Notifications

Notifications are disabled by default. When enabled, PrintSentinel schedules alerts after a confirmed failure screenshot, CSV row, terminal warning, and printer response are handled. Notification failures are logged as warnings and never block the configured printer stop or pause action. Provider results are appended to `logs/notifications.csv` with timestamp, event timestamp, provider, destination, success, and message fields.

Screenshot attachments are capped by `NOTIFICATION_MAX_SCREENSHOT_MB` and default to `5.0`. If a screenshot is missing or larger than the configured limit, Telegram and email providers fall back to text-only alerts.

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
export PRINTSENTINEL_NOTIFICATION_MAX_SCREENSHOT_MB=5
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
export PRINTSENTINEL_NOTIFICATION_MAX_SCREENSHOT_MB=5
python main.py
```

For Gmail, use an app password rather than your normal account password. `SMTP_SECURITY=starttls` with port `587` is also supported.

### Notification Troubleshooting

- Windows: confirm Windows notifications are enabled for the app name and that `windows-toasts` is installed in the active virtual environment.
- Telegram: confirm the bot token, chat ID, and bot membership in the target chat. Use the settings window `Test Notification` button before a real print.
- Gmail SMTP: use a Gmail app password, not your account password. Check whether SSL on port `465` or STARTTLS on port `587` matches your account or workspace policy.
- Attachments: if Telegram or email arrives without an image, check that the screenshot exists and is smaller than `NOTIFICATION_MAX_SCREENSHOT_MB`.
- Result logs: check `logs/notifications.csv` for provider-level success or failure messages.

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
