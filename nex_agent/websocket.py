"""
Nex Agent — WebSocket Manager v2.0
=====================================
User-isolated connections with reconnection support.
When a client disconnects and reconnects, it can resume receiving
the streaming response from where it left off.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("nex_agent.websocket")


class NexConnectionManager:
    """
    Manages WebSocket connections per user.
    Supports reconnection with message replay.
    """

    def __init__(self) -> None:
        # user_id -> list of active WebSocket connections
        self.connections: Dict[str, List[WebSocket]] = {}
        self.active_conversations: Dict[str, str] = {}
        self._streaming_manager = None  # Set after initialization
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_streaming_manager(self, streaming_manager) -> None:
        """Wire the streaming manager for replay support."""
        self._streaming_manager = streaming_manager

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        conversation_id: Optional[str] = None,
        last_message_id: Optional[str] = None,
    ) -> None:
        """
        Accept a WebSocket connection. If last_message_id is provided,
        replay any content generated since the client disconnected.
        """
        await websocket.accept()
        self._loop = asyncio.get_running_loop()

        if user_id not in self.connections:
            self.connections[user_id] = []
        self.connections[user_id].append(websocket)
        if conversation_id:
            self.active_conversations[user_id] = conversation_id

        total = sum(len(v) for v in self.connections.values())
        logger.info(f"WebSocket connected for user {user_id[:8]}... ({total} total)")

        # Replay missed content if client is reconnecting
        if last_message_id and self._streaming_manager:
            await self._replay_missed_content(websocket, last_message_id)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Remove connection. The stream continues generating on the server —
        tokens are still being persisted to DB even without an active client.
        """
        if user_id in self.connections:
            self.connections[user_id] = [
                ws for ws in self.connections[user_id] if ws != websocket
            ]
            if not self.connections[user_id]:
                del self.connections[user_id]
                self.active_conversations.pop(user_id, None)

        total = sum(len(v) for v in self.connections.values())
        logger.info(f"WebSocket disconnected for user {user_id[:8]}... ({total} total)")

    async def send_to_user(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        Send data to all active connections for this user.
        If no connections exist (user navigated away), nothing is sent
        but the streaming continues and saves to DB.
        """
        if user_id not in self.connections:
            return

        dead_connections = []
        for ws in self.connections[user_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead_connections.append(ws)

        for ws in dead_connections:
            self.connections[user_id] = [
                c for c in self.connections[user_id] if c != ws
            ]
        if user_id in self.connections and not self.connections[user_id]:
            del self.connections[user_id]
            self.active_conversations.pop(user_id, None)

    def dispatch_to_user(self, user_id: str, data: Dict[str, Any], timeout_seconds: float = 5.0) -> bool:
        """
        Thread-safe dispatch helper for background workers and monitor threads.
        """
        if user_id not in self.connections:
            return False

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop is self._loop:
            running_loop.create_task(self.send_to_user(user_id, data))
            return True

        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.send_to_user(user_id, data), self._loop)
            future.result(timeout=timeout_seconds)
            return True

        return False

    def set_active_conversation(self, user_id: str, conversation_id: str) -> None:
        if user_id and conversation_id:
            self.active_conversations[user_id] = conversation_id

    def get_active_conversation(self, user_id: str) -> str:
        return self.active_conversations.get(user_id, "")

    async def broadcast_token(
        self, user_id: str, message_id: str, token: str
    ) -> None:
        """
        Send a token to all active connections for this user.
        """
        await self.send_to_user(user_id, {
            "type": "token",
            "message_id": message_id,
            "token": token,
        })

    async def send_stream_event(
        self, user_id: str, message_id: str, event_type: str, data: Dict[str, Any]
    ) -> None:
        """Send a typed event (status, tool_call, done, error) to the user."""
        await self.send_to_user(user_id, {
            "type": event_type,
            "message_id": message_id,
            **data,
        })

    async def _replay_missed_content(
        self, websocket: WebSocket, last_message_id: str
    ) -> None:
        """
        When a client reconnects, send all content generated while they were away.
        """
        if not self._streaming_manager:
            return

        state = self._streaming_manager.get_stream_state(last_message_id)

        try:
            if state.status == "streaming":
                await websocket.send_json({
                    "type": "replay",
                    "message_id": last_message_id,
                    "content": state.content,
                    "status": "streaming",
                })
            elif state.status == "complete":
                await websocket.send_json({
                    "type": "replay",
                    "message_id": last_message_id,
                    "content": state.content,
                    "status": "complete",
                    "tool_calls": state.tool_calls,
                })
            elif state.status == "error":
                await websocket.send_json({
                    "type": "replay",
                    "message_id": last_message_id,
                    "content": state.content,
                    "status": "error",
                    "error": state.error_detail,
                })
            logger.info(f"Replayed {state.status} content for message {last_message_id[:8]}...")
        except Exception as e:
            logger.warning(f"Failed to replay content: {e}")

    def has_active_connections(self, user_id: Optional[str] = None) -> bool:
        """Check if there are active connections (optionally for a specific user)."""
        if user_id:
            return bool(self.connections.get(user_id))
        return any(self.connections.values())

    @property
    def active_connections(self) -> List[WebSocket]:
        """Backward compatibility — returns flat list of all connections."""
        all_conns = []
        for conns in self.connections.values():
            all_conns.extend(conns)
        return all_conns


# Module-level singleton
ws_manager = NexConnectionManager()
