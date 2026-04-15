"""
Arc Agent — WebSocket Manager
=================================
Manages WebSocket connections for real-time Arc Agent chat.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger("arc_agent.websocket")


class ArcWSManager:
    """Manages WebSocket connections for Arc Agent."""

    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = {}  # user_id -> [ws]
        self._streaming_manager: Optional[Any] = None

    def set_streaming_manager(self, sm) -> None:
        self._streaming_manager = sm

    async def connect(self, websocket: WebSocket,
                       user_id: str = "anonymous",
                       last_message_id: Optional[str] = None) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)
        logger.info(f"WebSocket connected: {user_id} (total: {self._total_connections()})")

        # Replay missed messages if reconnecting
        if last_message_id and self._streaming_manager:
            try:
                missed = self._streaming_manager.get_messages_after(last_message_id)
                for msg in missed:
                    await websocket.send_json({
                        "type": "replay",
                        "message": msg,
                    })
            except Exception as e:
                logger.warning(f"Replay failed: {e}")

    def disconnect(self, websocket: WebSocket, user_id: str = "anonymous") -> None:
        """Remove a WebSocket connection."""
        conns = self._connections.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns and user_id in self._connections:
            del self._connections[user_id]
        logger.info(f"WebSocket disconnected: {user_id}")

    async def send_to_user(self, user_id: str, data: Dict[str, Any]) -> None:
        """Send data to all connections of a specific user."""
        conns = self._connections.get(user_id, [])
        dead = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.remove(ws)

    async def broadcast_token(self, user_id: str,
                                message_id: str, token: str) -> None:
        """Stream a token to the user."""
        await self.send_to_user(user_id, {
            "type": "token",
            "message_id": message_id,
            "content": token,
        })

    async def send_stream_event(self, user_id: str,
                                  message_id: str,
                                  event_type: str,
                                  data: Dict[str, Any]) -> None:
        """Send a stream event (tool_call, status, done, error)."""
        await self.send_to_user(user_id, {
            "type": event_type,
            "message_id": message_id,
            **data,
        })

    async def broadcast_all(self, data: Dict[str, Any]) -> None:
        """Broadcast to all connected users."""
        for user_id in list(self._connections.keys()):
            await self.send_to_user(user_id, data)

    def _total_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())

    def get_connected_users(self) -> List[str]:
        return list(self._connections.keys())


# Singleton
arc_ws_manager = ArcWSManager()
