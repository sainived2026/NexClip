"""
Arc Agent — Core Orchestrator
=================================
Singleton controller that initializes all subsystems and
coordinates them. Mirrors Nex Agent's architecture.

Subsystems:
  1. ToolExecutor         — Arc-specific tools
  2. ConversationEngine   — LLM function calling loop
  3. Memory               — Persistent conversation + decision history
  4. SubAgentRegistry     — Pipeline sub-agent management
  5. SelfExpander          — Runtime capability creation
  6. WebSocket Manager    — Real-time chat
  7. StreamingManager     — Persistent message storage
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("arc_agent.core")

# Ensure project root is on path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
BACKEND_PATH = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)


class ArcAgent:
    """The living intelligence controller of Nexearch."""

    _instance: Optional["ArcAgent"] = None

    def __init__(self, memory_path: Optional[str] = None) -> None:
        self._boot_time = time.time()
        self.status = "initializing"

        # Memory path
        self._memory_path = memory_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "arc_agent_memory")
        os.makedirs(self._memory_path, exist_ok=True)

        # Subsystems (initialized on startup)
        self.tool_executor = None
        self.conversation_engine = None
        self.memory = None
        self.sub_agent_registry = None
        self.self_expander = None
        self.streaming_manager = None

    @classmethod
    def get_instance(cls, **kwargs) -> "ArcAgent":
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # ── Startup ─────────────────────────────────────────────────

    def startup(self) -> None:
        """Full startup sequence."""
        logger.info("=== Arc Agent v1.0 — Starting Up ===")
        start = time.time()

        # 1. Tool Executor
        from nexearch.arc.tool_executor import ArcToolExecutor
        self.tool_executor = ArcToolExecutor()

        # 2. Register all tools
        self._register_tools()

        # 3. Memory
        from nexearch.arc.memory import ArcMemory
        self.memory = ArcMemory(memory_path=self._memory_path)
        logger.info("Memory system initialized")

        # 4. Sub-Agent Registry
        from nexearch.arc.sub_agents.manager import SubAgentRegistry
        self.sub_agent_registry = SubAgentRegistry()
        logger.info(f"Sub-agent registry: {len(self.sub_agent_registry.get_all_agents())} agents")

        # 5. Self-Expander
        from nexearch.arc.self_expander import ArcSelfExpander
        self.self_expander = ArcSelfExpander(
            tool_executor=self.tool_executor,
            memory_path=os.path.join(self._memory_path, "custom_tools"),
        )
        loaded = self.self_expander.load_all_custom_tools()
        if loaded:
            logger.info(f"Loaded {loaded} custom tools")

        # 6. Streaming Manager
        from nexearch.arc.streaming_manager import ArcStreamingManager
        self.streaming_manager = ArcStreamingManager(
            storage_path=os.path.join(self._memory_path, "streams"),
        )
        self.streaming_manager.cleanup_stale_streams()
        logger.info("Streaming manager initialized")

        # 7. Conversation Engine (wired last)
        from nexearch.arc.conversation_engine import ArcConversationEngine
        self.conversation_engine = ArcConversationEngine(
            tool_executor=self.tool_executor,
            memory=self.memory,
        )
        logger.info("Conversation engine wired")

        elapsed = int((time.time() - start) * 1000)
        self.status = "online"

        tool_count = self.tool_executor.get_tool_count()
        categories = self.tool_executor.get_tool_categories()
        logger.info(
            f"=== Arc Agent ONLINE — {tool_count} tools across "
            f"{len(categories)} categories — {elapsed}ms ==="
        )
        for cat, count in sorted(categories.items()):
            logger.info(f"    {cat}: {count} tools")

    def _register_tools(self) -> None:
        """Register all Arc Agent tools."""
        from nexearch.arc.tools.arc_tools import register_all_arc_tools
        count = register_all_arc_tools(self.tool_executor)
        logger.info(f"Registered {count} Arc Agent tools")

        # Register self-expansion tools
        self._register_meta_tools()

    def _register_meta_tools(self) -> None:
        """Register meta-tools (self-expansion, sub-agent management)."""

        def _create_custom_tool(name: str, description: str,
                                 code: str, parameters: str = "{}") -> Dict:
            import json as _json
            if not self.self_expander:
                return {"error": "Self-expander not initialized"}
            try:
                params = _json.loads(parameters) if isinstance(parameters, str) else parameters
            except Exception:
                params = {}
            return self.self_expander.create_tool(name, description, code, params)

        def _list_custom_tools() -> Dict:
            if not self.self_expander:
                return {"tools": []}
            return {"tools": self.self_expander.list_custom_tools()}

        def _remove_custom_tool(tool_id: str) -> Dict:
            if not self.self_expander:
                return {"error": "Self-expander not initialized"}
            return self.self_expander.remove_tool(tool_id)

        def _list_sub_agents() -> Dict:
            if not self.sub_agent_registry:
                return {"agents": []}
            return {"agents": self.sub_agent_registry.get_all_agents()}

        def _sub_agent_task_history(limit: int = 20) -> Dict:
            if not self.sub_agent_registry:
                return {"history": []}
            return {"history": self.sub_agent_registry.get_task_history(limit)}

        def _search_tools(query: str) -> Dict:
            return {"tools": self.tool_executor.search_tools(query)}

        self.tool_executor.register("arc_create_custom_tool", "Create a custom tool at runtime from Python code. The newly created tool will be immediately available to call using its returned tool_id.", "meta", _create_custom_tool,
            {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "code": {"type": "string"}, "parameters": {"type": "string", "default": "{}"}}, "required": ["name", "description", "code"]})
        self.tool_executor.register("arc_list_custom_tools", "List all custom tools created by Arc Agent.", "meta", _list_custom_tools,
            {"type": "object", "properties": {}, "required": []})
        self.tool_executor.register("arc_remove_custom_tool", "Remove a custom tool completely.", "meta", _remove_custom_tool,
            {"type": "object", "properties": {"tool_id": {"type": "string"}}, "required": ["tool_id"]})
        self.tool_executor.register("arc_list_sub_agents", "List all sub-agents and their status.", "meta", _list_sub_agents,
            {"type": "object", "properties": {}, "required": []})
        self.tool_executor.register("arc_sub_agent_tasks", "Get sub-agent task history.", "meta", _sub_agent_task_history,
            {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}, "required": []})
        self.tool_executor.register("arc_search_tools", "Search Arc Agent's available tools.", "meta", _search_tools,
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})

    # ── Public Interface ────────────────────────────────────────

    def chat(self, message: str, context: Optional[Dict] = None) -> str:
        """Synchronous chat."""
        if not self.conversation_engine:
            return "Arc Agent is not fully initialized yet."
        return self.conversation_engine.chat(message, context)

    def chat_stream(self, message: str, context: Optional[Dict] = None):
        """Streaming chat generator."""
        import json
        if not self.conversation_engine:
            yield json.dumps({"type": "token", "content": "Arc Agent is not fully initialized yet."})
            yield json.dumps({"type": "done"})
            return
        yield from self.conversation_engine.chat_stream(message, context)

    def get_status(self) -> Dict[str, Any]:
        uptime = int(time.time() - self._boot_time)
        return {
            "status": self.status,
            "uptime_seconds": uptime,
            "tool_count": self.tool_executor.get_tool_count() if self.tool_executor else 0,
            "tool_categories": self.tool_executor.get_tool_categories() if self.tool_executor else {},
            "sub_agents": len(self.sub_agent_registry.get_all_agents()) if self.sub_agent_registry else 0,
            "custom_tools": len(self.self_expander.list_custom_tools()) if self.self_expander else 0,
            "subsystems": {
                "tool_executor": self.tool_executor is not None,
                "conversation_engine": self.conversation_engine is not None,
                "memory": self.memory is not None,
                "sub_agent_registry": self.sub_agent_registry is not None,
                "self_expander": self.self_expander is not None,
                "streaming_manager": self.streaming_manager is not None,
            },
        }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        if self.conversation_engine:
            return self.conversation_engine.get_history(limit)
        return []

    def clear_history(self) -> None:
        if self.conversation_engine:
            self.conversation_engine.clear_history()

    def shutdown(self) -> None:
        logger.info("=== Arc Agent shutting down ===")
        self.status = "offline"


# ── Module-level convenience ────────────────────────────────

_arc_agent: Optional[ArcAgent] = None


def get_arc_agent(**kwargs) -> ArcAgent:
    global _arc_agent
    if _arc_agent is None:
        _arc_agent = ArcAgent.get_instance(**kwargs)
    return _arc_agent
