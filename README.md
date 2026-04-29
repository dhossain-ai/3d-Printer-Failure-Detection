# PrintSentinel

PrintSentinel is a Python MVP for camera/video-based 3D print failure detection.

## Current Features

- Tkinter source selection for sample video, webcam, or mobile camera URL
- YOLO model loading from `models/model.pt`
- OpenCV detection loop with annotated video
- Multi-frame confirmation before failure status
- Failure labels for classes like `spaghetti`, `stringing`, and `zits`
- Failure screenshots saved to `captures/`
- Confirmed failure events appended to `logs/events.csv`
- Cooldown to avoid repeated screenshots, logs, and actions
- Terminal alert plus simulated printer stop or pause action
- Graceful handling for missing files and bad sources
- Quit monitoring with `q`

## Folder Structure

```text
printer_fail_demo/
├── main.py
├── config.py
├── ui.py
├── detector.py
├── runner.py
├── actions.py
├── sources.py
├── models/
│   └── model.pt
├── assets/
│   └── demo.mp4
├── captures/
└── logs/
    └── events.csv
```

## Setup And Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Configure cooldown and simulated response in `config.py`:

```python
ALERT_COOLDOWN_SECONDS = 20
SIMULATED_ACTION = "stop"
```
