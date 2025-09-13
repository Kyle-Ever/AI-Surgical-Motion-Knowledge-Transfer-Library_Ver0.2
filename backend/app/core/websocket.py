"""WebSocket connection manager.

Provides per-analysis connection lists and helper methods to send progress
events. The broadcast method also normalizes progress payload keys so that
clients can rely on `step` and `status` while keeping backward compatibility
with older `step_status` payloads.
"""

from fastapi import WebSocket
from typing import Dict, List
import json


class ConnectionManager:
    """Manage WebSocket connections per analysis_id."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, analysis_id: str):
        """Accept and register a connection for the given analysis_id."""
        await websocket.accept()
        self.active_connections.setdefault(analysis_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, analysis_id: str):
        """Remove a connection and cleanup registry if empty."""
        conns = self.active_connections.get(analysis_id)
        if not conns:
            return
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            del self.active_connections[analysis_id]

    async def send_progress(self, analysis_id: str, data: dict):
        """Send a progress event to all connections of analysis_id."""
        conns = self.active_connections.get(analysis_id)
        if not conns:
            return
        dead: List[WebSocket] = []
        for connection in conns:
            try:
                await connection.send_json(data)
            except Exception:
                dead.append(connection)
        for c in dead:
            self.disconnect(c, analysis_id)

    async def broadcast(self, message: str):
        """Broadcast a message to all connections.

        For progress events, ensure `step` and `status` keys exist while
        preserving older `step_status` for backward compatibility.
        """
        for analysis_id, conns in list(self.active_connections.items()):
            for connection in list(conns):
                try:
                    data = json.loads(message) if isinstance(message, str) else message
                    if isinstance(data, dict) and data.get("type") == "progress":
                        step_status = data.get("step_status")
                        if step_status and "step" not in data:
                            data["step"] = step_status
                        if "status" not in data:
                            data["status"] = (
                                step_status if step_status in ("completed", "failed") else "processing"
                            )
                    await connection.send_json(data)
                except Exception:
                    # best-effort broadcast; ignore individual connection errors
                    pass


# Global instance
manager = ConnectionManager()

