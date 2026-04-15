"""
Nex Agent Tools — Agent Communication (Category 6)
======================================================
Send and receive messages via the IACL command bus.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.agent")

# Reference to the live command bus (set during registration)
_command_bus = None


def _send_agent_message(to_agent: str, message_type: str, payload: str = "{}") -> Dict[str, Any]:
    import json
    if _command_bus is None:
        return {"sent": False, "error": "Command bus not initialized"}
    try:
        parsed = json.loads(payload) if isinstance(payload, str) else payload
        msg_id = _command_bus.send(
            from_agent="nex_agent", to_agent=to_agent,
            action=message_type, params=parsed,
        )
        # Log to AgentBus for monitoring
        try:
            from nex_agent.agent_bus import get_agent_bus
            bus = get_agent_bus()
            bus.nex_to_arc(
                f"[{message_type}] {json.dumps(parsed)[:200]}",
                msg_type="task_delegation",
            )
        except Exception:
            pass
        return {"sent": True, "message_id": msg_id, "to": to_agent, "type": message_type}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def _broadcast_to_all_agents(message_type: str, payload: str = "{}") -> Dict[str, Any]:
    import json
    if _command_bus is None:
        return {"sent_count": 0, "error": "Command bus not initialized"}
    try:
        parsed = json.loads(payload) if isinstance(payload, str) else payload
        agents = _command_bus.get_all_agents()
        sent = 0
        failed = []
        for agent in agents:
            agent_id = agent.get("id") or agent.get("name", "")
            if agent_id == "nex_agent":
                continue
            try:
                _command_bus.send(from_agent="nex_agent", to_agent=agent_id, action=message_type, params=parsed)
                sent += 1
            except Exception as e:
                failed.append(f"{agent_id}: {e}")
        # Log broadcast to AgentBus
        try:
            from nex_agent.agent_bus import get_agent_bus
            bus = get_agent_bus()
            bus.log("nex_agent", "system", "chat",
                    f"Broadcast [{message_type}] to {sent} agents")
        except Exception:
            pass
        return {"sent_count": sent, "failed": failed}
    except Exception as e:
        return {"sent_count": 0, "error": str(e)}


def _get_agent_status(agent_id: str) -> Dict[str, Any]:
    if _command_bus is None:
        return {"online": False, "error": "Command bus not initialized"}
    agents = _command_bus.get_all_agents()
    for a in agents:
        if (a.get("id") or a.get("name", "")) == agent_id:
            return {"online": True, "agent": a}
    return {"online": False, "error": f"Agent '{agent_id}' not found"}


def _list_all_agents() -> Dict[str, Any]:
    if _command_bus is None:
        return {"agents": [], "error": "Command bus not initialized"}
    agents = _command_bus.get_all_agents()
    return {"agents": agents, "count": len(agents)}


def register(executor: "ToolExecutor", command_bus=None) -> int:
    global _command_bus
    _command_bus = command_bus

    executor.register(name="send_agent_message", description="Send a message to a specific agent via the IACL command bus.", category="agent", handler=_send_agent_message, parameters={"type": "object", "properties": {"to_agent": {"type": "string"}, "message_type": {"type": "string"}, "payload": {"type": "string", "default": "{}"}}, "required": ["to_agent", "message_type"]})
    executor.register(name="broadcast_to_all_agents", description="Broadcast a message to all registered agents.", category="agent", handler=_broadcast_to_all_agents, parameters={"type": "object", "properties": {"message_type": {"type": "string"}, "payload": {"type": "string", "default": "{}"}}, "required": ["message_type"]})
    executor.register(name="get_agent_status", description="Get the status of a specific agent.", category="agent", handler=_get_agent_status, parameters={"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]})
    executor.register(name="list_all_agents", description="List all registered agents and their status.", category="agent", handler=_list_all_agents, parameters={"type": "object", "properties": {}})
    return 4
