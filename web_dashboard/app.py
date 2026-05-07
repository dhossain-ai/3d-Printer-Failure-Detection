"""FastAPI application for PrintSentinel dashboard."""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path

import config
from creality_status import fetch_creality_status
from creality_control import CrealityWebSocketControlClient
from printer_controller import log_printer_command as log_command


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="PrintSentinel Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class LightRequest(BaseModel):
    enabled: bool

class FanRequest(BaseModel):
    fan: str
    percent: int

class StopRequest(BaseModel):
    confirm: str


@app.get("/")
def read_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"config": config}
    )


@app.get("/api/config")
def get_config():
    """Returns safe config for frontend logic."""
    return {
        "camera_configured": bool(config.PRINTER_CAMERA_URL),
        "status_ws_configured": bool(config.CREALITY_WS_URL),
        "control_enabled": config.CREALITY_CONTROL_ENABLED,
        "model_device": config.MODEL_DEVICE,
        "printer_camera_url": config.PRINTER_CAMERA_URL,
        "notifications_enabled": config.NOTIFICATIONS_ENABLED,
    }


@app.get("/api/status")
def get_status():
    """Fetches real-time Creality status."""
    if not config.CREALITY_WS_URL:
        return {"connected": False, "error": "CREALITY_WS_URL not configured"}
    
    result = fetch_creality_status(
        config.CREALITY_WS_URL, 
        timeout_seconds=config.CREALITY_STATUS_TIMEOUT_SECONDS
    )
    
    if not result:
        return {"connected": False, "error": "Could not fetch status"}
        
    return {"connected": True, "status": result}


def get_creality_client():
    if not config.CREALITY_CONTROL_ENABLED:
        raise HTTPException(status_code=403, detail="Creality control is disabled")
    if not config.CREALITY_WS_URL:
        raise HTTPException(status_code=400, detail="CREALITY_WS_URL not configured")
    return CrealityWebSocketControlClient(
        ws_url=config.CREALITY_WS_URL,
        timeout_seconds=config.CREALITY_CONTROL_TIMEOUT_SECONDS
    )


@app.post("/api/control/light")
def control_light(req: LightRequest):
    client = get_creality_client()
    res = client.set_light(req.enabled)
    if not res.success:
        raise HTTPException(status_code=500, detail=res.message)
    return {"success": True, "action": res.action}


@app.post("/api/control/fan")
def control_fan(req: FanRequest):
    client = get_creality_client()
    
    percent = req.percent
    if not 0 <= percent <= 100:
        raise HTTPException(status_code=400, detail="Percent must be between 0 and 100")
        
    if req.fan == "model":
        res = client.set_model_fan_percent(percent)
    elif req.fan == "auxiliary":
        res = client.set_auxiliary_fan_percent(percent)
    elif req.fan == "case":
        res = client.set_case_fan_percent(percent)
    else:
        raise HTTPException(status_code=400, detail="Unknown fan type")
        
    if not res.success:
        raise HTTPException(status_code=500, detail=res.message)
    return {"success": True, "action": res.action}


@app.post("/api/control/pause")
def control_pause():
    client = get_creality_client()
    res = client.pause_print()
    log_command("creality_ws", "pause_print", res.success, res.message, res.response_preview)
    if not res.success:
        raise HTTPException(status_code=500, detail=res.message)
    return {"success": True, "action": res.action}


@app.post("/api/control/stop")
def control_stop(req: StopRequest):
    if req.confirm != "STOP":
        raise HTTPException(status_code=400, detail="Invalid confirmation")
    client = get_creality_client()
    res = client.stop_print()
    log_command("creality_ws", "stop_print", res.success, res.message, res.response_preview)
    if not res.success:
        raise HTTPException(status_code=500, detail=res.message)
    return {"success": True, "action": res.action}


@app.get("/api/files")
def get_files():
    client = get_creality_client()
    res = client.request_file_list()
    if not res.success:
        raise HTTPException(status_code=500, detail=res.message)
        
    files = []
    if res.response_preview:
        import json
        try:
            data = json.loads(res.response_preview)
            if "retGcodeFileInfo" in data:
                for file_info in data["retGcodeFileInfo"]:
                    if isinstance(file_info, dict) and "name" in file_info:
                        files.append(file_info)
        except Exception:
            pass
            
    return {
        "success": True, 
        "files": files, 
        "response_preview": res.response_preview,
        "message": res.message
    }


import csv
import os

def read_recent_csv(file_path: Path, limit: int = 20):
    if not file_path.exists():
        return []
    rows = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    return list(reversed(rows))[:limit]


@app.get("/api/events/recent")
def get_recent_events():
    events = read_recent_csv(config.EVENTS_CSV_PATH)
    return {"events": events}


@app.get("/api/notifications/recent")
def get_recent_notifications():
    notifications_path = config.LOGS_DIR / "notifications.csv"
    notifications = read_recent_csv(notifications_path)
    return {"notifications": notifications}


# ---------------------------------------------------------------------------
# AI Monitoring endpoints
# ---------------------------------------------------------------------------

from fastapi.responses import StreamingResponse
from web_dashboard.monitoring_service import get_service
import time


class AiStartRequest(BaseModel):
    camera_url: str = ""
    camera_type: str = "stream"


@app.post("/api/ai/start")
def ai_start(req: AiStartRequest):
    """Start background AI monitoring. Rejects if already running."""
    service = get_service()
    camera_url = req.camera_url.strip() or config.PRINTER_CAMERA_URL
    camera_type = req.camera_type or config.PRINTER_CAMERA_TYPE
    error = service.start(camera_url=camera_url, camera_type=camera_type)
    if error:
        raise HTTPException(status_code=409, detail=error)
    return {"success": True, "message": "AI monitoring started"}


@app.post("/api/ai/stop")
def ai_stop():
    """Stop the background AI monitoring thread."""
    service = get_service()
    service.stop()
    return {"success": True, "message": "AI monitoring stopped"}


@app.get("/api/ai/status")
def ai_status():
    """Return current AI monitoring state."""
    return get_service().get_status()


def _mjpeg_generator():
    """Yield MJPEG frames from the monitoring service."""
    service = get_service()
    placeholder = _placeholder_jpeg()
    while True:
        frame = service.get_latest_frame_jpeg()
        if frame is None:
            frame = placeholder
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
        )
        time.sleep(0.05)


def _placeholder_jpeg() -> bytes:
    """Return a tiny 1x1 grey JPEG as a placeholder when no frame is ready."""
    try:
        import cv2
        import numpy as np
        img = np.full((240, 320, 3), 50, dtype=np.uint8)
        cv2.putText(img, "AI monitoring stopped", (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2, cv2.LINE_AA)
        _, buf = cv2.imencode(".jpg", img)
        return buf.tobytes()
    except Exception:
        # Minimal valid 1x1 grey JPEG if cv2 is not available
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n"
            b"\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d"
            b"\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e\x00"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f"
            b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00"
            b"\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03"
            b"\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91\xa1\x08#B\xb1"
            b"\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&'()*456789:CDEFG"
            b"HIJKLMNOPQRSTUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\x03\xff\xd9"
        )


@app.get("/api/ai/stream")
def ai_stream():
    """MJPEG annotated camera stream from the AI monitoring service."""
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
