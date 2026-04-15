"""
Nex Agent — Decision Engine
================================
Evaluates incoming alerts, reasons about action,
and routes decisions through the appropriate channels.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import logging

from nex_agent.memory import NexMemory

logger = logging.getLogger("nex_agent.decision_engine")


class DecisionEngine:
    """
    Reasoning and priority logic for Nex Agent.

    Responsibilities:
    - Evaluate alert severity and decide: auto-resolve, delegate, or escalate
    - Maintain decision log with reasoning
    - Priority arbitration for concurrent requests
    """

    def __init__(self, memory: NexMemory) -> None:
        self.memory = memory
        self._pending_queue: List[Dict[str, Any]] = []

    def evaluate_alert(
        self,
        severity: str,
        source: str,
        issue: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate an incoming alert and decide on action.

        Returns: {action, reasoning, auto_resolved}
        """
        action = "escalate"
        reasoning = ""
        auto_resolved = False

        if severity == "low":
            action = "log_only"
            reasoning = f"Low severity alert from {source}: logged for tracking"
            auto_resolved = True

        elif severity == "medium":
            # Check if this is a recurring issue
            past_alerts = self.memory.get_active_alerts()
            similar = [a for a in past_alerts if source in a.get("source", "")]

            if len(similar) >= 3:
                action = "escalate"
                reasoning = f"Recurring medium alert from {source} ({len(similar)} similar alerts active) — escalating to admin"
            else:
                action = "monitor"
                reasoning = f"Medium alert from {source}: monitoring for recurrence"

        elif severity == "high":
            action = "delegate"
            reasoning = f"High severity from {source}: delegating to relevant agent for investigation"

        elif severity == "critical":
            action = "escalate"
            reasoning = f"CRITICAL alert from {source}: immediate admin notification required"

        # Log the decision
        self.memory.save_decision(
            decision_type="alert_evaluation",
            description=f"Alert from {source}: {issue}",
            reasoning=reasoning,
            alternatives=["auto-resolve", "delegate", "escalate", "monitor"],
            outcome=action,
            context={"severity": severity, "source": source, "issue": issue},
        )

        # Save alert
        alert_id = self.memory.save_alert(
            severity=severity,
            source=source,
            message=issue,
            resolved=auto_resolved,
            resolution="Auto-resolved (low severity)" if auto_resolved else "",
        )

        return {
            "action": action,
            "reasoning": reasoning,
            "auto_resolved": auto_resolved,
            "alert_id": alert_id,
        }



    def prioritize_requests(
        self, requests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Sort concurrent requests by priority.
        CRITICAL > HIGH > NORMAL > LOW
        Within same priority: ALERT > COMMAND > QUERY > REPORT
        """
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        type_order = {"ALERT": 0, "COMMAND": 1, "QUERY": 2, "REPORT": 3, "BROADCAST": 4}

        return sorted(
            requests,
            key=lambda r: (
                priority_order.get(r.get("priority", "normal"), 2),
                type_order.get(r.get("message_type", "QUERY"), 3),
            ),
        )

    def _log_directive_decision(
        self, directive: Dict[str, Any], approved: bool, reasoning: str,
    ) -> None:
        self.memory.save_decision(
            decision_type="directive_review",
            description=f"Directive for {directive.get('target_component', 'unknown')}",
            reasoning=reasoning,
            alternatives=["approve", "reject", "queue for human review"],
            outcome="approved" if approved else "rejected",
            context=directive,
        )
