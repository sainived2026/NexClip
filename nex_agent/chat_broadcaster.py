"""
Nex Agent — Chat Broadcaster
================================
Pushes proactive messages to all connected WebSocket sessions.
Used by the NotificationMonitor and notification tools.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger("nex_agent.chat_broadcaster")


class ChatBroadcaster:
    """
    Manages broadcasting messages to connected WebSocket clients.
    Integrates with the existing ws_manager from websocket.py.
    """

    def __init__(self, ws_manager=None) -> None:
        self._ws_manager = ws_manager
        self._message_queue: List[Dict[str, Any]] = []
        self._max_queue = 100

    def set_ws_manager(self, ws_manager) -> None:
        self._ws_manager = ws_manager

    def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected WebSocket clients.
        If no clients are connected, queue the message.
        """
        message.setdefault("timestamp", datetime.utcnow().isoformat())

        if self._ws_manager and hasattr(self._ws_manager, "active_connections"):
            if self._ws_manager.active_connections:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._send_to_all(message))
                except RuntimeError:
                    # No event loop — queue it
                    self._queue_message(message)
                return

        # No WebSocket manager or no connections — queue
        self._queue_message(message)

    async def _send_to_all(self, message: Dict[str, Any]) -> None:
        if not self._ws_manager:
            return
        for conn in list(self._ws_manager.active_connections):
            try:
                await conn.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket client: {e}")

    def _queue_message(self, message: Dict[str, Any]) -> None:
        self._message_queue.append(message)
        if len(self._message_queue) > self._max_queue:
            self._message_queue = self._message_queue[-self._max_queue:]

    def get_queued_messages(self, clear: bool = True) -> List[Dict[str, Any]]:
        """Get and optionally clear queued messages."""
        msgs = list(self._message_queue)
        if clear:
            self._message_queue.clear()
        return msgs

    def flush_queue(self) -> None:
        """Send all queued messages to connected clients."""
        if not self._ws_manager or not hasattr(self._ws_manager, "active_connections"):
            return
        if not self._ws_manager.active_connections:
            return

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            for msg in self._message_queue:
                loop.create_task(self._send_to_all(msg))
            self._message_queue.clear()
        except RuntimeError:
            pass
