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
├── sources.py
├── utils.py
├── tests/
│   ├── test_actions.py
│   ├── test_printer_controller.py
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

## Demo Workflow

1. Start the app with `python main.py`.
2. Choose `Sample video`.
3. Watch the overlay for source, status, fail frame counter, latest detection, and cooldown.
4. Press `q` to quit the monitoring window.
5. Check `captures/` for failure screenshots.
6. Check `logs/events.csv` for event rows.

## Screenshots

Add portfolio screenshots here after running the app:

- Source selection menu
- Monitoring window in `STATUS: MONITORING`
- Confirmed failure window in `STATUS: FAIL DETECTED -> STOP PRINTER`
- Example `logs/events.csv` row

## Tests

```bash
pytest -q
```

The test suite covers safe filename generation, cooldown behavior, CSV row creation, event log writing, and simulated action routing. It does not require a webcam, live OpenCV window, or YOLO model execution.

HTTP controller tests use mocked request sessions and do not require a real printer.

## Roadmap

- Add mocked runner tests for confirmed failure orchestration
- Add optional authentication/header support for HTTP printer endpoints
- Add calibration guidance for custom models and camera placement
- Add optional UI controls for cooldown and simulated action mode
- Add richer screenshot examples for GitHub documentation
