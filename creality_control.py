"""Safe WebSocket control client for Creality K1C."""

import json
import logging
from dataclasses import dataclass

import websocket

logger = logging.getLogger(__name__)


import time

def has_file_list_response(message: str) -> bool:
    try:
        data = json.loads(message)
        if isinstance(data, dict) and "retGcodeFileInfo" in data:
            return True
    except Exception:
        pass
    return False

def clamp_percent(value: int) -> int:
    return max(0, min(100, value))

def percent_to_pwm(percent: int) -> int:
    return round(clamp_percent(percent) * 255 / 100)

def build_fan_gcode(fan_index: int, percent: int) -> str:
    pwm = percent_to_pwm(percent)
    return f"M106 P{fan_index} S{pwm}"

@dataclass
class CrealityCommandResult:
    action: str
    success: bool
    message: str
    response_preview: str | None = None


class CrealityWebSocketControlClient:
    def __init__(self, ws_url: str, timeout_seconds: float = 5):
        self.ws_url = ws_url
        self.timeout_seconds = timeout_seconds

    def _send_command(self, action: str, method: str, params: dict, wait_for_key: str | None = None) -> CrealityCommandResult:
        payload = {"method": method, "params": params}
        
        try:
            ws = websocket.create_connection(self.ws_url, timeout=self.timeout_seconds)
            try:
                ws.send(json.dumps(payload))
                response_preview = None
                message_text = "Command sent successfully"
                
                try:
                    if wait_for_key == "retGcodeFileInfo":
                        start_time = time.time()
                        while time.time() - start_time < self.timeout_seconds:
                            # Adjust timeout for this specific recv to avoid blocking past the total deadline
                            remaining = self.timeout_seconds - (time.time() - start_time)
                            if remaining <= 0:
                                break
                            ws.settimeout(remaining)
                            
                            response = ws.recv()
                            response_str = response if isinstance(response, str) else str(response)
                            
                            if has_file_list_response(response_str):
                                response_preview = response_str[:200] + ("..." if len(response_str) > 200 else "")
                                break
                        else:
                            message_text = f"Command sent but {wait_for_key} response was not observed"
                    else:
                        response = ws.recv()
                        response_str = response if isinstance(response, str) else str(response)
                        response_preview = response_str[:200] + ("..." if len(response_str) > 200 else "")
                except Exception as e:
                    logger.debug(f"No response received or timeout for {action}: {e}")
                    if wait_for_key and response_preview is None:
                        message_text = f"Command sent but {wait_for_key} response was not observed"
                    
                return CrealityCommandResult(
                    action=action,
                    success=True,
                    message=message_text,
                    response_preview=response_preview
                )
            finally:
                ws.close()
        except Exception as e:
            logger.error(f"Failed to send Creality command {action}: {e}")
            return CrealityCommandResult(
                action=action,
                success=False,
                message=str(e)
            )

    def set_light(self, enabled: bool) -> CrealityCommandResult:
        return self._send_command(
            action=f"light_{'on' if enabled else 'off'}",
            method="set",
            params={"lightSw": 1 if enabled else 0}
        )

    def set_model_fan(self, enabled: bool) -> CrealityCommandResult:
        return self._send_command(
            action=f"model_fan_{'on' if enabled else 'off'}",
            method="set",
            params={"fan": 1 if enabled else 0}
        )

    def set_model_fan_percent(self, percent: int) -> CrealityCommandResult:
        return self._send_command(
            action=f"model_fan_{clamp_percent(percent)}pct",
            method="set",
            params={"gcodeCmd": build_fan_gcode(0, percent)}
        )

    def set_auxiliary_fan(self, enabled: bool) -> CrealityCommandResult:
        return self._send_command(
            action=f"auxiliary_fan_{'on' if enabled else 'off'}",
            method="set",
            params={"fanAuxiliary": 1 if enabled else 0}
        )

    def set_auxiliary_fan_percent(self, percent: int) -> CrealityCommandResult:
        return self._send_command(
            action=f"auxiliary_fan_{clamp_percent(percent)}pct",
            method="set",
            params={"gcodeCmd": build_fan_gcode(1, percent)}
        )

    def set_case_fan(self, enabled: bool) -> CrealityCommandResult:
        return self._send_command(
            action=f"case_fan_{'on' if enabled else 'off'}",
            method="set",
            params={"fanCase": 1 if enabled else 0}
        )

    def set_case_fan_percent(self, percent: int) -> CrealityCommandResult:
        return self._send_command(
            action=f"case_fan_{clamp_percent(percent)}pct",
            method="set",
            params={"gcodeCmd": build_fan_gcode(2, percent)}
        )

    def request_file_list(self) -> CrealityCommandResult:
        return self._send_command(
            action="request_file_list",
            method="get",
            params={"reqGcodeFile": 1},
            wait_for_key="retGcodeFileInfo"
        )
