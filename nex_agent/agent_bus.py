"""
Nex Agent — Inter-Agent Communication Bus (IACB)
====================================================
Centralized message bus that captures ALL agent-to-agent
communication (Nex ↔ Arc, Arc ↔ Sub-agents) and streams
them to connected monitoring clients via WebSocket.

Every tool call between agents, every delegation, every
status update flows through this bus so the admin can
watch the agents think and collaborate in real-time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import WebSocket

logger = logging.getLogger("nex_agent.agent_bus")

# ── Agent Identity Constants ────────────────────────────────
AGENT_NEX = "nex_agent"
AGENT_ARC = "arc_agent"
AGENT_USER = "user"
AGENT_SYSTEM = "system"
AGENT_CELERY = "celery_worker"

# Sub-agents under Arc
AGENT_SCRAPE = "scrape_agent"
AGENT_ANALYSIS = "analysis_agent"
AGENT_SCORING = "scoring_agent"
AGENT_EVOLUTION = "evolution_agent"
AGENT_BRIDGE = "bridge_agent"
AGENT_PUBLISHER = "publisher_agent"

# ── Message Types ───────────────────────────────────────────
MSG_CHAT = "chat"                    # Agent-to-agent conversation
MSG_TASK = "task_delegation"         # Delegating a task
MSG_STATUS = "status_update"         # Progress/status update
MSG_TOOL_CALL = "tool_call"          # Agent invoking a tool
MSG_TOOL_RESULT = "tool_result"      # Result of a tool call
MSG_PIPELINE = "pipeline_event"      # Pipeline stage transition
MSG_NOTIFICATION = "notification"    # Proactive notification to user
MSG_ERROR = "error"                  # Error report

# ── Agent Display Info ──────────────────────────────────────
AGENT_DISPLAY = {
    AGENT_NEX:       {"name": "Nex Agent",       "color": "#6366F1", "icon": "🧠"},
    AGENT_ARC:       {"name": "Arc Agent",       "color": "#8B5CF6", "icon": "🔮"},
    AGENT_USER:      {"name": "Admin",           "color": "#10B981", "icon": "👤"},
    AGENT_SYSTEM:    {"name": "System",          "color": "#F59E0B", "icon": "⚙️"},
    AGENT_CELERY:    {"name": "Celery Worker",   "color": "#EF4444", "icon": "🔧"},
    AGENT_SCRAPE:    {"name": "Scrape Agent",    "color": "#06B6D4", "icon": "🕷️"},
    AGENT_ANALYSIS:  {"name": "Analysis Agent",  "color": "#0EA5E9", "icon": "📊"},
    AGENT_SCORING:   {"name": "Scoring Agent",   "color": "#14B8A6", "icon": "🎯"},
    AGENT_EVOLUTION: {"name": "Evolution Agent", "color": "#F97316", "icon": "🧬"},
    AGENT_BRIDGE:    {"name": "Bridge Agent",    "color": "#EC4899", "icon": "🌉"},
    AGENT_PUBLISHER: {"name": "Publisher Agent", "color": "#A855F7", "icon": "📤"},
}


class BusMessage:
    """A single message on the agent bus."""

    __slots__ = (
        "id", "from_agent", "to_agent", "message_type",
        "content", "metadata", "timestamp",
    )

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.id = str(uuid.uuid4())[:12]
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.message_type = message_type
        self.content = content
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        from_info = AGENT_DISPLAY.get(self.from_agent, {"name": self.from_agent, "color": "#9CA3AF", "icon": "🤖"})
        to_info = AGENT_DISPLAY.get(self.to_agent, {"name": self.to_agent, "color": "#9CA3AF", "icon": "🤖"})

        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "from_name": from_info["name"],
            "from_color": from_info["color"],
            "from_icon": from_info["icon"],
            "to_agent": self.to_agent,
            "to_name": to_info["name"],
            "to_color": to_info["color"],
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class AgentBus:
    """
    Central communication bus for all inter-agent messages.

    Features:
    - In-memory ring buffer (last 500 messages)
    - File persistence to agent_bus_log.jsonl
    - WebSocket broadcast to monitoring clients
    - Thread-safe logging from sync contexts
    """

    _instance: Optional["AgentBus"] = None

    def __init__(self, max_buffer: int = 500) -> None:
        self._buffer: Deque[BusMessage] = deque(maxlen=max_buffer)
        self._monitor_connections: List[WebSocket] = []
        self._log_path = (
            Path(__file__).resolve().parent / "nex_agent_memory" / "agent_bus_log.jsonl"
        )
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("AgentBus initialized")

    @classmethod
    def get_instance(cls) -> "AgentBus":
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Core Logging ────────────────────────────────────────

    def log(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BusMessage:
        """
        Log a message to the bus. Works from both sync and async contexts.
        Automatically broadcasts to all monitoring WebSocket clients.
        """
        msg = BusMessage(from_agent, to_agent, message_type, content, metadata)
        self._buffer.append(msg)

        # Persist to file
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(msg.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Bus log write failed: {e}")

        # Console log for terminal visibility
        from_name = AGENT_DISPLAY.get(from_agent, {}).get("name", from_agent)
        to_name = AGENT_DISPLAY.get(to_agent, {}).get("name", to_agent)
        logger.info(f"🔗 [{from_name} → {to_name}] ({message_type}) {content[:120]}")

        # Broadcast to monitoring WebSocket clients
        self._try_broadcast(msg)

        return msg

    def _try_broadcast(self, msg: BusMessage) -> None:
        """Attempt to broadcast to monitoring WebSockets (handles sync/async contexts)."""
        if not self._monitor_connections:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast_to_monitors(msg))
        except RuntimeError:
            # No event loop — try creating one for the broadcast
            try:
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(self._broadcast_to_monitors(msg))
                new_loop.close()
            except Exception:
                pass  # Non-critical — message is still in buffer

    async def _broadcast_to_monitors(self, msg: BusMessage) -> None:
        """Send message to all connected monitoring clients."""
        dead = []
        data = msg.to_dict()
        for ws in self._monitor_connections:
            try:
                await ws.send_json({"type": "bus_message", **data})
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._monitor_connections.remove(ws)

    # ── Monitor WebSocket Management ────────────────────────

    async def connect_monitor(self, websocket: WebSocket) -> None:
        """Register a monitoring WebSocket client."""
        await websocket.accept()
        self._monitor_connections.append(websocket)

        # Send recent history
        history = [m.to_dict() for m in self._buffer]
        await websocket.send_json({
            "type": "bus_history",
            "messages": history[-100:],  # Last 100 messages
        })

        logger.info(f"Agent Monitor connected ({len(self._monitor_connections)} total)")

    def disconnect_monitor(self, websocket: WebSocket) -> None:
        """Unregister a monitoring WebSocket client."""
        if websocket in self._monitor_connections:
            self._monitor_connections.remove(websocket)
        logger.info(f"Agent Monitor disconnected ({len(self._monitor_connections)} total)")

    # ── Query Methods ───────────────────────────────────────

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent messages from the buffer."""
        messages = list(self._buffer)
        return [m.to_dict() for m in messages[-limit:]]

    def get_by_agent(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages involving a specific agent."""
        matches = [
            m for m in self._buffer
            if m.from_agent == agent_id or m.to_agent == agent_id
        ]
        return [m.to_dict() for m in matches[-limit:]]

    def get_by_type(self, message_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages of a specific type."""
        matches = [m for m in self._buffer if m.message_type == message_type]
        return [m.to_dict() for m in matches[-limit:]]

    def clear(self) -> int:
        """Clear the buffer. Returns count of cleared messages."""
        count = len(self._buffer)
        self._buffer.clear()
        return count

    # ── Convenience Logging Methods ─────────────────────────

    def nex_to_arc(self, content: str, msg_type: str = MSG_CHAT, **meta) -> BusMessage:
        """Shorthand: Nex Agent → Arc Agent."""
        return self.log(AGENT_NEX, AGENT_ARC, msg_type, content, meta or None)

    def arc_to_nex(self, content: str, msg_type: str = MSG_CHAT, **meta) -> BusMessage:
        """Shorthand: Arc Agent → Nex Agent."""
        return self.log(AGENT_ARC, AGENT_NEX, msg_type, content, meta or None)

    def nex_to_user(self, content: str, msg_type: str = MSG_NOTIFICATION, **meta) -> BusMessage:
        """Shorthand: Nex Agent → User (proactive message)."""
        return self.log(AGENT_NEX, AGENT_USER, msg_type, content, meta or None)

    def pipeline_event(self, from_agent: str, content: str, **meta) -> BusMessage:
        """Log a pipeline stage transition."""
        return self.log(from_agent, AGENT_SYSTEM, MSG_PIPELINE, content, meta or None)

    def tool_call(self, agent: str, tool_name: str, args: Dict = None) -> BusMessage:
        """Log a tool invocation."""
        return self.log(
            agent, AGENT_SYSTEM, MSG_TOOL_CALL,
            f"Calling `{tool_name}`",
            {"tool": tool_name, "args": args or {}},
        )

    def tool_result(self, agent: str, tool_name: str, result_summary: str) -> BusMessage:
        """Log a tool result."""
        return self.log(
            AGENT_SYSTEM, agent, MSG_TOOL_RESULT,
            f"`{tool_name}` → {result_summary}",
            {"tool": tool_name},
        )


# ── Module-level singleton accessor ─────────────────────────

def get_agent_bus() -> AgentBus:
    """Get the singleton AgentBus instance."""
    return AgentBus.get_instance()
