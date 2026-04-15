"""
Agent Communication Bridge
==============================
Bidirectional HTTP communication between Nex Agent (port 8001)
and Arc Agent (port 8003). Each agent can call the other via
REST endpoints for chat, tool execution, and status queries.

This module provides the bridge from BOTH sides —
Nex Agent uses ArcBridge, Arc Agent uses NexBridge.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from loguru import logger


class AgentBridge:
    """Base HTTP bridge between agents."""

    def __init__(self, target_url: str, target_name: str,
                 timeout: int = 30) -> None:
        self.target_url = target_url.rstrip("/")
        self.target_name = target_name
        self.timeout = timeout

    def _get_client(self):
        import httpx
        return httpx.Client(timeout=self.timeout)

    def chat(self, message: str, client_id: str = "") -> Dict[str, Any]:
        """Send a chat message to the target agent."""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.target_url}/api/chat",
                    json={"message": message, "client_id": client_id},
                )
                return response.json()
        except Exception as e:
            logger.warning(f"Bridge chat to {self.target_name} failed: {e}")
            return {"error": str(e), "hint": f"Is {self.target_name} running?"}

    def status(self) -> Dict[str, Any]:
        """Get the target agent's status."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.target_url}/api/status")
                return response.json()
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    def health(self) -> Dict[str, Any]:
        """Check target agent health."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.target_url}/health")
                return response.json()
        except Exception as e:
            return {"status": "down", "error": str(e)}

    def execute_tool(self, tool_name: str,
                      arguments: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Execute a tool on the target agent."""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.target_url}/api/tools/execute",
                    params={"tool_name": tool_name},
                    json=arguments,
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    def list_tools(self) -> Dict[str, Any]:
        """List tools available on the target agent."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.target_url}/api/tools")
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    def search_tools(self, query: str) -> Dict[str, Any]:
        """Search tools on the target agent."""
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.target_url}/api/tools/search",
                    params={"query": query},
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_history(self, limit: int = 50) -> Dict[str, Any]:
        """Get conversation history from the target agent."""
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.target_url}/api/history",
                    params={"limit": limit},
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}


class ArcBridge(AgentBridge):
    """Nex Agent → Arc Agent bridge."""

    def __init__(self) -> None:
        url = os.environ.get("ARC_AGENT_URL", "http://localhost:8003")
        timeout = int(os.environ.get("AGENT_BRIDGE_TIMEOUT_SECONDS", "30"))
        super().__init__(url, "Arc Agent", timeout)

    def get_sub_agents(self) -> Dict[str, Any]:
        """Get Arc Agent's sub-agents."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.target_url}/api/sub-agents")
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_sub_agent_tasks(self, limit: int = 20) -> Dict[str, Any]:
        """Get recent sub-agent tasks."""
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.target_url}/api/sub-agents/tasks",
                    params={"limit": limit},
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    def get_pipeline_runs(self, limit: int = 20) -> Dict[str, Any]:
        """Get Arc Agent's recent pipeline runs."""
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.target_url}/api/memory/pipeline-runs",
                    params={"limit": limit},
                )
                return response.json()
        except Exception as e:
            return {"error": str(e)}


class NexBridge(AgentBridge):
    """Arc Agent → Nex Agent bridge."""

    def __init__(self) -> None:
        url = os.environ.get("NEXEARCH_NEX_AGENT_URL", "http://localhost:8001")
        timeout = int(os.environ.get("AGENT_BRIDGE_TIMEOUT_SECONDS", "30"))
        super().__init__(url, "Nex Agent", timeout)

    def request_writing(self, platform: str, content_type: str,
                         topic: str, client_id: str = "",
                         context: str = "") -> Dict[str, Any]:
        """Request Nex Agent's enterprise writing tools (titles, captions, etc)."""
        return self.chat(
            f"Generate a {content_type} for {platform}. Topic: {topic}. "
            f"Client: {client_id}. Context: {context}",
            client_id=client_id,
        )

    def report_issue(self, severity: str, message: str,
                      source: str = "arc_agent") -> Dict[str, Any]:
        """Report an issue to Nex Agent."""
        return self.chat(
            f"[ALERT] [{severity.upper()}] from {source}: {message}",
        )

    def request_caption_style(self, clip_path: str,
                               caption_style: str) -> Dict[str, Any]:
        """Ask Nex Agent to apply a caption style to a clip."""
        return self.chat(
            f"Apply caption style '{caption_style}' to the clip at {clip_path} "
            f"and return the path to the styled clip.",
        )


# ── Singletons ─────────────────────────────────────────────

_arc_bridge: Optional[ArcBridge] = None
_nex_bridge: Optional[NexBridge] = None


def get_arc_bridge() -> ArcBridge:
    """Get the Nex→Arc bridge (used by Nex Agent to talk to Arc Agent)."""
    global _arc_bridge
    if _arc_bridge is None:
        _arc_bridge = ArcBridge()
    return _arc_bridge


def get_nex_bridge() -> NexBridge:
    """Get the Arc→Nex bridge (used by Arc Agent to talk to Nex Agent)."""
    global _nex_bridge
    if _nex_bridge is None:
        _nex_bridge = NexBridge()
    return _nex_bridge
