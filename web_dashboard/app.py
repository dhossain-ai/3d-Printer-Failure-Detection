"""FastAPI application for PrintSentinel dashboard."""

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pathlib import Path

import config
from creality_status import fetch_creality_status
from creality_control import CrealityWebSocketControlClient


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="PrintSentinel Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class LightRequest(BaseModel):
    enabled: bool

class FanRequest(BaseModel):
    fan: str
    percent: int


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
