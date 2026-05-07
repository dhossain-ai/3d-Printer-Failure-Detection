"""Safe WebSocket control client for Creality K1C."""

import json
import logging
from dataclasses import dataclass

import websocket

logger = logging.getLogger(__name__)


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

    def _send_command(self, action: str, method: str, params: dict) -> CrealityCommandResult:
        payload = {"method": method, "params": params}
        
        try:
            ws = websocket.create_connection(self.ws_url, timeout=self.timeout_seconds)
            try:
                ws.send(json.dumps(payload))
                try:
                    response = ws.recv()
                    # Truncate response_preview
                    if isinstance(response, str):
                        response_preview = response[:200] + ("..." if len(response) > 200 else "")
                    else:
                        response_preview = str(response)[:200] + ("..." if len(str(response)) > 200 else "")
                except Exception as e:
                    logger.debug(f"No response received or timeout for {action}: {e}")
                    response_preview = None
                    
                return CrealityCommandResult(
                    action=action,
                    success=True,
                    message="Command sent successfully",
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

    def set_auxiliary_fan(self, enabled: bool) -> CrealityCommandResult:
        return self._send_command(
            action=f"auxiliary_fan_{'on' if enabled else 'off'}",
            method="set",
            params={"fanAuxiliary": 1 if enabled else 0}
        )

    def set_case_fan(self, enabled: bool) -> CrealityCommandResult:
        return self._send_command(
            action=f"case_fan_{'on' if enabled else 'off'}",
            method="set",
            params={"fanCase": 1 if enabled else 0}
        )

    def request_file_list(self) -> CrealityCommandResult:
        return self._send_command(
            action="request_file_list",
            method="get",
            params={"reqGcodeFile": 1}
        )
