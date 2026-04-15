"""
Nex Agent Tools — Notifications (Category 7)
================================================
Send proactive messages and schedule condition-based notifications.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.notification")

# References set during registration
_broadcaster = None
_monitor = None


def _send_chat_notification(message: str, priority: str = "info", rich_type: str = "") -> Dict[str, Any]:
    """Send a proactive message to the user's active chat session."""
    if _broadcaster is None:
        return {"sent": False, "error": "Chat broadcaster not initialized"}
    try:
        _broadcaster.broadcast({
            "type": "notification",
            "priority": priority,
            "message": message,
            "rich_type": rich_type or None,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return {"sent": True, "priority": priority, "delivery_confirmed": True}
    except Exception as e:
        return {"sent": False, "error": str(e)}


def _schedule_notification(
    message: str, condition_type: str, condition_params: str = "{}",
    check_interval_seconds: int = 10, fire_once: bool = True, priority: str = "info",
) -> Dict[str, Any]:
    """Schedule a condition-based notification."""
    if _monitor is None:
        return {"scheduled": False, "error": "Notification monitor not initialized"}

    import json
    try:
        params = json.loads(condition_params) if isinstance(condition_params, str) else condition_params
    except Exception:
        params = {}

    monitor_id = f"mon_{uuid.uuid4().hex[:8]}"
    _monitor.add_condition(
        monitor_id=monitor_id,
        condition_type=condition_type,
        condition_params=params,
        message=message,
        priority=priority,
        fire_once=fire_once,
        check_interval=check_interval_seconds,
    )
    return {"scheduled": True, "monitor_id": monitor_id, "condition_type": condition_type}


def _cancel_scheduled_notification(monitor_id: str) -> Dict[str, Any]:
    if _monitor is None:
        return {"cancelled": False, "error": "Notification monitor not initialized"}
    result = _monitor.remove_condition(monitor_id)
    return {"cancelled": result, "monitor_id": monitor_id}


def _get_scheduled_notifications() -> Dict[str, Any]:
    if _monitor is None:
        return {"monitors": [], "error": "Notification monitor not initialized"}
    return {"monitors": _monitor.list_conditions()}


def register(executor: "ToolExecutor", broadcaster=None, monitor=None) -> int:
    global _broadcaster, _monitor
    _broadcaster = broadcaster
    _monitor = monitor

    executor.register(name="send_chat_notification", description="Send a proactive message to the user's active chat session. Use this to notify the user about events even if they didn't ask.", category="notification", handler=_send_chat_notification, parameters={"type": "object", "properties": {"message": {"type": "string"}, "priority": {"type": "string", "enum": ["info", "warning", "critical"], "default": "info"}, "rich_type": {"type": "string", "default": ""}}, "required": ["message"]})
    executor.register(name="schedule_notification", description="Register a condition-based notification. Nex Agent will monitor the condition and send the message when it becomes true.", category="notification", handler=_schedule_notification, parameters={"type": "object", "properties": {"message": {"type": "string"}, "condition_type": {"type": "string", "enum": ["service_online", "custom"]}, "condition_params": {"type": "string", "default": "{}"}, "check_interval_seconds": {"type": "integer", "default": 10}, "fire_once": {"type": "boolean", "default": True}, "priority": {"type": "string", "default": "info"}}, "required": ["message", "condition_type"]})
    executor.register(name="cancel_scheduled_notification", description="Cancel a pending scheduled notification.", category="notification", handler=_cancel_scheduled_notification, parameters={"type": "object", "properties": {"monitor_id": {"type": "string"}}, "required": ["monitor_id"]})
    executor.register(name="get_scheduled_notifications", description="List all active monitoring conditions.", category="notification", handler=_get_scheduled_notifications, parameters={"type": "object", "properties": {}})
    return 4
