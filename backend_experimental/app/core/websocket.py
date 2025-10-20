"""WebSocket connection manager.

Provides per-analysis connection lists and helper methods to send progress
events. The broadcast method also normalizes progress payload keys so that
clients can rely on `step` and `status` while keeping backward compatibility
with older `step_status` payloads.
"""

from fastapi import WebSocket
from typing import Dict, List, Optional
import json
import time
import asyncio


class ConnectionManager:
    """Manage WebSocket connections per analysis_id with optimized updates."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # スロットリング用の最終更新時刻を記録
        self.last_update_time: Dict[str, float] = {}
        # バッチ更新用のペンディングデータ
        self.pending_updates: Dict[str, dict] = {}
        # 最小更新間隔（秒）
        self.min_update_interval = 0.5  # 0.5秒間隔に制限

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
        """Send a progress event to all connections of analysis_id with throttling."""
        conns = self.active_connections.get(analysis_id)
        if not conns:
            return

        # スロットリング：最小間隔をチェック
        current_time = time.time()
        last_time = self.last_update_time.get(analysis_id, 0)

        # 重要な更新（完了、失敗、ステップ変更）は即座に送信
        is_important = (
            data.get("status") in ("completed", "failed") or
            data.get("progress") == 100 or
            data.get("progress") == 0 or
            data.get("type") == "error"
        )

        # 通常の進捗更新はスロットリング
        if not is_important and current_time - last_time < self.min_update_interval:
            # ペンディングに追加（最新データで上書き）
            self.pending_updates[analysis_id] = data
            # 遅延送信をスケジュール
            await asyncio.sleep(self.min_update_interval - (current_time - last_time))
            # ペンディングがあれば送信
            if analysis_id in self.pending_updates:
                data = self.pending_updates.pop(analysis_id)
                current_time = time.time()

        # 最終更新時刻を記録
        self.last_update_time[analysis_id] = current_time

        # 実際の送信処理
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

