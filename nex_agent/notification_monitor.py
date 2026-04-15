"""
Nex Agent — Notification Monitor
====================================
Background async task that evaluates registered conditions
and fires notifications when conditions become true.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("nex_agent.notification_monitor")


class MonitorCondition:
    """A registered condition to monitor."""

    def __init__(
        self,
        monitor_id: str,
        condition_type: str,
        condition_params: Dict[str, Any],
        message: str,
        priority: str = "info",
        fire_once: bool = True,
        check_interval: int = 10,
    ) -> None:
        self.monitor_id = monitor_id
        self.condition_type = condition_type
        self.condition_params = condition_params
        self.message = message
        self.priority = priority
        self.fire_once = fire_once
        self.check_interval = check_interval
        self.created_at = datetime.utcnow().isoformat()
        self.last_checked: Optional[str] = None
        self.last_value: Any = None
        self.fired = False


class NotificationMonitor:
    """
    Runs as a background async task alongside the main Nex Agent process.
    Continuously evaluates registered conditions and fires notifications.
    """

    def __init__(self, tool_executor=None, broadcaster=None) -> None:
        self._conditions: Dict[str, MonitorCondition] = {}
        self._tool_executor = tool_executor
        self._broadcaster = broadcaster
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start the monitoring loop as a background task."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop())
            logger.info("NotificationMonitor started")
        except RuntimeError:
            logger.warning("No event loop — NotificationMonitor not started")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("NotificationMonitor stopped")

    async def _run_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                now = time.time()
                for mid, cond in list(self._conditions.items()):
                    if cond.fired and cond.fire_once:
                        continue
                    try:
                        triggered, value = await self._evaluate(cond)
                        cond.last_checked = datetime.utcnow().isoformat()
                        cond.last_value = value

                        if triggered and not cond.fired:
                            await self._fire(cond, value)
                            cond.fired = True
                            if cond.fire_once:
                                logger.info(f"Monitor {mid} fired (once) — removing")
                    except Exception as e:
                        logger.error(f"Monitor {mid} evaluation failed: {e}")
            except Exception as e:
                logger.error(f"NotificationMonitor loop error: {e}")

            await asyncio.sleep(5)

    async def _evaluate(self, cond: MonitorCondition) -> tuple:
        """Evaluate a condition. Returns (triggered: bool, value: Any)."""
        if not self._tool_executor:
            return False, None

        if cond.condition_type == "service_online":
            service = cond.condition_params.get("service")
            result = self._tool_executor.execute_sync("check_process_health", {"service": service})
            online = result.data.get("online", False)
            return online, {"online": online, "service": service}

        elif cond.condition_type == "custom":
            # Custom conditions can check arbitrary things
            return False, None

        return False, None

    async def _fire(self, cond: MonitorCondition, value: Any) -> None:
        """Send the notification."""
        message = cond.message
        try:
            if value and isinstance(value, dict):
                message = message.format(**value)
        except (KeyError, IndexError):
            pass

        logger.info(f"🔔 Notification fired [{cond.priority}]: {message}")

        if self._broadcaster:
            self._broadcaster.broadcast({
                "type": "notification",
                "priority": cond.priority,
                "message": message,
                "monitor_id": cond.monitor_id,
                "timestamp": datetime.utcnow().isoformat(),
            })

    # ── Public API ──────────────────────────────────────────────

    def add_condition(
        self,
        monitor_id: str,
        condition_type: str,
        condition_params: Dict[str, Any],
        message: str,
        priority: str = "info",
        fire_once: bool = True,
        check_interval: int = 10,
    ) -> None:
        self._conditions[monitor_id] = MonitorCondition(
            monitor_id=monitor_id,
            condition_type=condition_type,
            condition_params=condition_params,
            message=message,
            priority=priority,
            fire_once=fire_once,
            check_interval=check_interval,
        )
        logger.info(f"Monitor registered: {monitor_id} ({condition_type})")

    def remove_condition(self, monitor_id: str) -> bool:
        if monitor_id in self._conditions:
            del self._conditions[monitor_id]
            return True
        return False

    def list_conditions(self) -> List[Dict[str, Any]]:
        return [
            {
                "monitor_id": c.monitor_id,
                "condition_type": c.condition_type,
                "message": c.message,
                "priority": c.priority,
                "created_at": c.created_at,
                "last_checked": c.last_checked,
                "last_value": c.last_value,
                "fired": c.fired,
            }
            for c in self._conditions.values()
        ]
