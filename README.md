# PrintSentinel

PrintSentinel is a Python MVP for camera/video-based 3D print failure detection.

## Current Phase 1 Features

- Tkinter source selection for sample video, webcam, or mobile camera URL
- YOLO model loading from `models/model.pt`
- OpenCV detection loop with annotated video
- Multi-frame confirmation before failure status
- Failure labels for classes like `spaghetti`, `stringing`, and `zits`
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
