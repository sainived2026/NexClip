"""
Nex Agent — Inter-Agent Communication Layer (IACL)
====================================================
Async message bus connecting all agents.
In-process asyncio queues for single-machine deployment.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import logging

logger = logging.getLogger("nex_agent.command_bus")


class MessageType(str, Enum):
    COMMAND = "COMMAND"
    QUERY = "QUERY"
    REPORT = "REPORT"
    ALERT = "ALERT"
    BROADCAST = "BROADCAST"


class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class AgentLevel(int, Enum):
    SOVEREIGN = 0   # Nex Agent
    DIRECTOR = 1
    SPECIALIST = 2
    SERVICE = 3     # Backend/Frontend Agents


class AgentMessage:
    """Structured inter-agent message."""

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        priority: Priority,
        payload: Dict[str, Any],
        reply_to: Optional[str] = None,
        requires_ack: bool = False,
        timeout_ms: int = 30000,
    ) -> None:
        self.message_id = str(uuid.uuid4())[:12]
        self.timestamp = datetime.utcnow().isoformat()
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.message_type = message_type
        self.priority = priority
        self.payload = payload
        self.reply_to = reply_to
        self.requires_ack = requires_ack
        self.timeout_ms = timeout_ms
        self.acknowledged = False
        self.response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "from": self.from_agent,
            "to": self.to_agent,
            "message_type": self.message_type.value,
            "priority": self.priority.value,
            "payload": self.payload,
            "reply_to": self.reply_to,
            "requires_ack": self.requires_ack,
            "timeout_ms": self.timeout_ms,
        }


class AgentRegistration:
    """Registered agent on the command bus."""

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        level: AgentLevel,
        handler: Optional[Callable] = None,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.level = level
        self.handler = handler
        self.status = "idle"
        self.current_task = ""
        self.health_score = 100
        self.last_heartbeat = datetime.utcnow().isoformat()
        self.missed_heartbeats = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "level": self.level.value,
            "status": self.status,
            "current_task": self.current_task,
            "health_score": self.health_score,
            "last_heartbeat": self.last_heartbeat,
        }


class CommandBus:
    """
    Central message bus for inter-agent communication.

    Features:
    - Agent registration and discovery
    - Priority-based message routing (Nex Agent always first)
    - Heartbeat aggregation
    - Message logging
    - Broadcast support
    """

    def __init__(self) -> None:
        self.agents: Dict[str, AgentRegistration] = {}
        self.message_log: List[Dict[str, Any]] = []
        self._max_log_size = 1000
        self._listeners: Dict[str, List[Callable]] = {}  # agent_id -> handlers

    # ── Agent Management ────────────────────────────────────────

    def register_agent(
        self,
        agent_id: str,
        agent_name: str,
        level: AgentLevel,
        handler: Optional[Callable] = None,
    ) -> None:
        """Register an agent on the bus."""
        self.agents[agent_id] = AgentRegistration(agent_id, agent_name, level, handler)
        logger.info(f"Agent registered: {agent_name} ({agent_id}) — Level {level.name}")

    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from the bus."""
        if agent_id in self.agents:
            name = self.agents[agent_id].agent_name
            del self.agents[agent_id]
            logger.info(f"Agent unregistered: {name}")

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        agent = self.agents.get(agent_id)
        return agent.to_dict() if agent else None

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get status of all registered agents."""
        return [a.to_dict() for a in sorted(self.agents.values(), key=lambda a: a.level.value)]

    # ── Messaging ───────────────────────────────────────────────

    def send(self, message: AgentMessage) -> str:
        """
        Send a message to a target agent.
        Returns the message_id.
        """
        # Validate sender authority
        sender = self.agents.get(message.from_agent)
        receiver = self.agents.get(message.to_agent)

        if sender and receiver and message.message_type == MessageType.COMMAND:
            if sender.level.value > receiver.level.value:
                logger.warning(
                    f"Authority violation: {sender.agent_name} (L{sender.level.value}) "
                    f"cannot COMMAND {receiver.agent_name} (L{receiver.level.value})"
                )
                # Lower agents can only send REPORT and ALERT upward
                if message.message_type not in (MessageType.REPORT, MessageType.ALERT):
                    return ""

        # Log the message
        self._log_message(message)

        # Route to handler
        if message.to_agent == "*":
            # Broadcast
            for agent_id, agent in self.agents.items():
                if agent_id != message.from_agent and agent.handler:
                    try:
                        agent.handler(message)
                    except Exception as e:
                        logger.error(f"Broadcast handler error for {agent_id}: {e}")
        else:
            target = self.agents.get(message.to_agent)
            if target and target.handler:
                try:
                    target.handler(message)
                except Exception as e:
                    logger.error(f"Handler error for {message.to_agent}: {e}")

        return message.message_id

    def broadcast(
        self,
        from_agent: str,
        payload: Dict[str, Any],
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """Send a broadcast to all agents."""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent="*",
            message_type=MessageType.BROADCAST,
            priority=priority,
            payload=payload,
        )
        return self.send(msg)

    def send_command(
        self,
        to_agent: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """Convenience: send a COMMAND from Nex Agent."""
        msg = AgentMessage(
            from_agent="nex_agent",
            to_agent=to_agent,
            message_type=MessageType.COMMAND,
            priority=priority,
            payload={"action": action, "params": params or {}},
        )
        return self.send(msg)

    def send_alert(
        self,
        from_agent: str,
        issue: str,
        severity: str = "high",
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send an alert to Nex Agent."""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent="nex_agent",
            message_type=MessageType.ALERT,
            priority=Priority.CRITICAL if severity == "critical" else Priority.HIGH,
            payload={"issue": issue, "severity": severity, "context": context or {}},
        )
        return self.send(msg)

    # ── Heartbeats ──────────────────────────────────────────────

    def heartbeat(
        self,
        agent_id: str,
        status: str = "idle",
        current_task: str = "",
        health_score: int = 100,
    ) -> None:
        """Process a heartbeat from an agent."""
        agent = self.agents.get(agent_id)
        if agent:
            agent.status = status
            agent.current_task = current_task
            agent.health_score = health_score
            agent.last_heartbeat = datetime.utcnow().isoformat()
            agent.missed_heartbeats = 0

    def check_heartbeats(self, timeout_seconds: int = 90) -> List[str]:
        """Check for agents with missed heartbeats. Returns list of dead agent IDs."""
        dead_agents = []
        now = datetime.utcnow()

        for agent_id, agent in self.agents.items():
            if agent_id == "nex_agent":
                continue  # Nex Agent doesn't heartbeat to itself

            try:
                last = datetime.fromisoformat(agent.last_heartbeat)
                elapsed = (now - last).total_seconds()
                if elapsed > timeout_seconds:
                    agent.missed_heartbeats += 1
                    if agent.missed_heartbeats >= 3:
                        dead_agents.append(agent_id)
                        agent.status = "dead"
                        logger.warning(f"Agent {agent.agent_name} missed {agent.missed_heartbeats} heartbeats")
            except Exception:
                continue

        return dead_agents

    # ── Message Log ─────────────────────────────────────────────

    def _log_message(self, message: AgentMessage) -> None:
        self.message_log.append(message.to_dict())
        if len(self.message_log) > self._max_log_size:
            self.message_log = self.message_log[-self._max_log_size:]

    def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.message_log[-limit:]

    def get_agent_messages(self, agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        msgs = [
            m for m in self.message_log
            if m["from"] == agent_id or m["to"] == agent_id
        ]
        return msgs[-limit:]

    def get_activity_feed(self, limit: int = 10) -> str:
        """Formatted activity feed for LLM context."""
        recent = self.get_recent_messages(limit)
        if not recent:
            return "No recent agent activity."
        lines = []
        for m in recent:
            lines.append(
                f"- [{m['timestamp'][-8:]}] {m['from']} → {m['to']}: "
                f"{m['message_type']} — {json.dumps(m['payload'])[:100]}"
            )
        return "\n".join(lines)
