"""
Arc Agent — Sub-Agent Manager
=================================
Manages the 6 pipeline sub-agents and any dynamically created sub-agents.
Coordinates task delegation, status tracking, and inter-sub-agent messaging.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger


class SubAgentTask:
    """A task assigned to a sub-agent."""

    def __init__(self, agent_id: str, action: str,
                 params: Dict[str, Any]) -> None:
        self.task_id = str(uuid.uuid4())[:12]
        self.agent_id = agent_id
        self.action = action
        self.params = params
        self.status = "pending"
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "params": self.params,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class SubAgentRegistry:
    """Registry of all sub-agents under Arc Agent."""

    # Built-in sub-agents (from the pipeline)
    BUILT_IN_AGENTS = {
        "scrape_agent": {
            "name": "Deep Scrape Agent",
            "description": "Scrapes 100+ posts from social accounts using 3 methods",
            "capabilities": ["apify_scrape", "api_scrape", "playwright_scrape", "buffer_scrape"],
            "platforms": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"],
        },
        "analysis_agent": {
            "name": "Content Analysis Agent",
            "description": "LLM-powered content pattern analysis and categorization",
            "capabilities": ["analyze_post", "detect_patterns", "extract_hooks"],
        },
        "scoring_agent": {
            "name": "Scoring & DNA Agent",
            "description": "5-dimension scoring rubric and Account DNA synthesis",
            "capabilities": ["score_posts", "synthesize_dna", "tier_classification"],
        },
        "evolution_agent": {
            "name": "Evolution Agent",
            "description": "Dual-mode self-evolution engine (client + universal)",
            "capabilities": ["client_evolution", "universal_evolution", "rubric_update"],
        },
        "bridge_agent": {
            "name": "NexClip Bridge Agent",
            "description": "Converts DNA to ClipDirectives for NexClip",
            "capabilities": ["create_directive", "inject_prompt", "update_style"],
        },
        "publisher_agent": {
            "name": "Publisher Agent",
            "description": "Automated publishing via 3 methods",
            "capabilities": ["metricool_publish", "api_publish", "playwright_publish", "buffer_publish"],
        },
    }

    def __init__(self) -> None:
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._task_history: List[SubAgentTask] = []
        self._message_log: List[Dict[str, Any]] = []

        # Register built-in agents
        for agent_id, info in self.BUILT_IN_AGENTS.items():
            self._agents[agent_id] = {
                **info,
                "status": "idle",
                "current_task": None,
                "task_count": 0,
                "health": 100,
                "type": "built_in",
            }

    def register_agent(self, agent_id: str, name: str,
                        description: str, capabilities: List[str]) -> None:
        """Register a new dynamic sub-agent."""
        self._agents[agent_id] = {
            "name": name,
            "description": description,
            "capabilities": capabilities,
            "status": "idle",
            "current_task": None,
            "task_count": 0,
            "health": 100,
            "type": "dynamic",
        }
        logger.info(f"Sub-agent registered: {name} ({agent_id})")

    def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get all sub-agents with their status."""
        return [
            {"agent_id": aid, **info}
            for aid, info in self._agents.items()
        ]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def assign_task(self, agent_id: str, action: str,
                     params: Dict[str, Any]) -> SubAgentTask:
        """Assign a task to a sub-agent."""
        task = SubAgentTask(agent_id, action, params)
        self._task_history.append(task)

        agent = self._agents.get(agent_id)
        if agent:
            agent["status"] = "working"
            agent["current_task"] = task.task_id
            agent["task_count"] += 1

        return task

    def complete_task(self, task_id: str, result: Dict[str, Any] = None,
                       error: str = None) -> None:
        """Mark a sub-agent task as complete."""
        for task in self._task_history:
            if task.task_id == task_id:
                task.status = "error" if error else "complete"
                task.result = result
                task.error = error
                task.completed_at = datetime.now(timezone.utc).isoformat()

                agent = self._agents.get(task.agent_id)
                if agent:
                    agent["status"] = "idle"
                    agent["current_task"] = None
                break

    def send_message(self, from_agent: str, to_agent: str,
                      message: Dict[str, Any]) -> None:
        """Send message between sub-agents."""
        self._message_log.append({
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_task_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._task_history[-limit:]]

    def get_message_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._message_log[-limit:]

    def find_agent_for_capability(self, capability: str) -> Optional[str]:
        """Find which sub-agent has a specific capability."""
        for agent_id, info in self._agents.items():
            if capability in info.get("capabilities", []):
                return agent_id
        return None
