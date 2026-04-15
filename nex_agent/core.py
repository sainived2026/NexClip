"""
Nex Agent — Core Orchestrator v3.0
======================================
Singleton controller that initializes all subsystems
and coordinates them for incoming requests.

Subsystems:
  1. ToolExecutor          — 49 real tools across 10 categories
  2. ConversationEngine    — LLM function calling loop
  3. NotificationMonitor   — Background proactive notifications
  4. ChatBroadcaster       — Push messages to WebSocket clients
  5. CodebaseKnowledgeIndex — Codebase awareness
  6. RuntimeMonitor        — Health polling
    7. Memory                — Persistent conversation history
    8. CommandBus            — Inter-agent communication
    9. SelfExpander          — Runtime capability creation
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from nex_agent.personality import STATUS_LABELS

logger = logging.getLogger("nex_agent.core")


class NexAgent:
    """The living master intelligence of NexClip."""

    _instance: Optional["NexAgent"] = None

    def __init__(
        self,
        project_root: Optional[str] = None,
        memory_path: Optional[str] = None,
        backend_url: str = "http://localhost:8000",
        frontend_url: str = "http://localhost:3000",
        db_path: str = "backend/nexclip.db",
    ) -> None:
        self.project_root = project_root or self._detect_project_root()
        self.backend_url = backend_url
        self.frontend_url = frontend_url
        self.db_path = os.path.join(self.project_root, db_path)
        self.status = "initializing"
        self._boot_time = time.time()

        # Memory path — always inside the nex_agent package directory
        _nex_agent_dir = str(Path(__file__).resolve().parent)
        self._memory_path = memory_path or os.path.join(_nex_agent_dir, "nex_agent_memory")
        os.makedirs(self._memory_path, exist_ok=True)

        # ── Initialize subsystems ───────────────────────────────
        from nex_agent.tool_executor import ToolExecutor
        from nex_agent.conversation_engine import ConversationEngine
        from nex_agent.notification_monitor import NotificationMonitor
        from nex_agent.chat_broadcaster import ChatBroadcaster
        from nex_agent.self_expander import SelfExpander

        # 1. Tool Executor — the heart of the agent
        self.tool_executor = ToolExecutor(project_root=self.project_root)

        # 2. Chat Broadcaster
        self.broadcaster = ChatBroadcaster()

        # 3. Notification Monitor
        self.notification_monitor = NotificationMonitor(
            tool_executor=self.tool_executor,
            broadcaster=self.broadcaster,
        )

        # 4. Self Expander
        self.self_expander = SelfExpander(tool_executor=self.tool_executor)

        # 5. Knowledge Index (lazy — may be slow)
        self.knowledge: Optional[Any] = None

        # 6. Runtime Monitor
        self.monitor: Optional[Any] = None

        # 7. Memory
        self.memory: Optional[Any] = None

        # 8. Command Bus
        self.command_bus: Optional[Any] = None

        # 9. Conversation Engine (wired after tool registration)
        self.conversation_engine: Optional[ConversationEngine] = None

        # 10. Streaming Manager — persistent streaming responses
        self.streaming_manager: Optional[Any] = None

    @classmethod
    def get_instance(cls, **kwargs) -> "NexAgent":
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def _detect_project_root(self) -> str:
        return str(Path(__file__).resolve().parent.parent)

    # ── Startup ─────────────────────────────────────────────────

    def startup(self) -> None:
        """Full startup sequence."""
        logger.info("=== Nex Agent v4.0 - Starting Up ===")
        start = time.time()

        # 1. Register all tools
        self._register_tools()

        # 2. Initialize remaining subsystems
        self._init_subsystems()

        # 3. Initialize streaming manager (DB persistence)
        self._init_streaming_manager()

        # 4. Wire conversation engine
        self._wire_conversation_engine()

        elapsed = int((time.time() - start) * 1000)
        self.status = "online"

        tool_count = self.tool_executor.get_tool_count()
        categories = self.tool_executor.get_tool_categories()
        logger.info(
            f"=== Nex Agent ONLINE - {tool_count} tools across "
            f"{len(categories)} categories - {elapsed}ms ==="
        )
        for cat, count in sorted(categories.items()):
            logger.info(f"    {cat}: {count} tools")

    def _register_tools(self) -> None:
        """Register all 10 tool categories."""
        from nex_agent.tools import register_all_tools

        # Standard tools (not needing special references)
        count = register_all_tools(self.tool_executor)
        logger.info(f"Registered {count} standard tools")

        # Re-register notification tools with live references
        from nex_agent.tools import notification_tools
        notification_tools.register(
            self.tool_executor,
            broadcaster=self.broadcaster,
            monitor=self.notification_monitor,
        )

    def _init_subsystems(self) -> None:
        """Initialize lazy subsystems."""
        # Knowledge Index
        try:
            from nex_agent.knowledge_index import CodebaseKnowledgeIndex
            self.knowledge = CodebaseKnowledgeIndex(
                project_root=self.project_root,
                index_path=os.path.join(self._memory_path, "codebase_index.json"),
            )
            self.knowledge.build_index()
            logger.info("Knowledge index built")
        except Exception as e:
            logger.warning(f"Knowledge index init failed: {e}")

        # Runtime Monitor
        try:
            from nex_agent.runtime_monitor import RuntimeMonitor
            self.monitor = RuntimeMonitor(
                backend_url=self.backend_url,
                frontend_url=self.frontend_url,
                db_path=self.db_path,
            )
            logger.info("Runtime monitor initialized")
        except Exception as e:
            logger.warning(f"Runtime monitor init failed: {e}")

        # Memory
        try:
            from nex_agent.memory import NexMemory
            self.memory = NexMemory(memory_path=self._memory_path)
            logger.info("Memory system initialized")
        except Exception as e:
            logger.warning(f"Memory init failed: {e}")

        # Command Bus
        try:
            from nex_agent.command_bus import CommandBus, AgentLevel
            self.command_bus = CommandBus()
            self.command_bus.register_agent(
                agent_id="nex_agent",
                agent_name="Nex Agent",
                level=AgentLevel.SOVEREIGN,
                handler=self._handle_incoming_message
            )

            # Re-register agent tools with bus reference
            from nex_agent.tools import agent_tools
            agent_tools.register(self.tool_executor, command_bus=self.command_bus)
            logger.info("Command bus initialized")
        except Exception as e:
            logger.warning(f"Command bus init failed: {e}")

    def _init_streaming_manager(self) -> None:
        """Initialize the persistent streaming manager and create DB tables."""
        try:
            from nex_agent.streaming_manager import StreamingManager

            self.streaming_manager = StreamingManager(db_path=self.db_path)

            # Ensure conversation tables exist
            from sqlalchemy import text
            session = self.streaming_manager._get_session()
            try:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS nex_conversations (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL DEFAULT '',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        model_used TEXT NOT NULL DEFAULT '',
                        is_deleted BOOLEAN NOT NULL DEFAULT 0,
                        deleted_at DATETIME,
                        message_count INTEGER NOT NULL DEFAULT 0
                    )
                """))
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS nex_messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'complete',
                        rich_type TEXT,
                        rich_data TEXT,
                        tool_calls TEXT,
                        error_detail TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        completed_at DATETIME,
                        token_count INTEGER DEFAULT 0,
                        FOREIGN KEY (conversation_id) REFERENCES nex_conversations(id) ON DELETE CASCADE
                    )
                """))
                session.commit()
                logger.info("Streaming manager initialized — DB tables verified")
            finally:
                session.close()

            # Clean up any stale streams from previous crashes
            self.streaming_manager.cleanup_stale_streams()

        except Exception as e:
            logger.warning(f"Streaming manager init failed: {e}")
            self.streaming_manager = None

    def _wire_conversation_engine(self) -> None:
        """Create conversation engine wired to all subsystems."""
        from nex_agent.conversation_engine import ConversationEngine

        self.conversation_engine = ConversationEngine(
            llm_provider=None,  # Uses singleton
            tool_executor=self.tool_executor,
            personality_builder=None,
            knowledge_index=self.knowledge,
            runtime_monitor=self.monitor,
            memory=self.memory,
        )
        logger.info("Conversation engine wired with tool executor")

    # ── Public Interface ────────────────────────────────────────

    def chat(self, message: str) -> str:
        if not self.conversation_engine:
            return "Nex Agent is not fully initialized yet."
        return self.conversation_engine.chat(message)

    def chat_stream(self, message: str):
        if not self.conversation_engine:
            import json
            yield json.dumps({"type": "token", "content": "Nex Agent is not fully initialized yet."})
            yield json.dumps({"type": "done"})
            return
        yield from self.conversation_engine.chat_stream(message)

    def get_status(self) -> Dict[str, Any]:
        uptime = int(time.time() - self._boot_time)
        model = "unknown"
        try:
            from nex_agent.llm_provider import get_llm_provider
            model = get_llm_provider().get_active_model()
        except Exception:
            pass

        return {
            "status": self.status,
            "status_label": STATUS_LABELS.get(self.status, {}).get("label", self.status.upper()),
            "uptime_seconds": uptime,
            "active_model": model,
            "tool_count": self.tool_executor.get_tool_count(),
            "tool_categories": self.tool_executor.get_tool_categories(),
            "subsystems": {
                "tool_executor": True,
                "conversation_engine": self.conversation_engine is not None,
                "notification_monitor": self.notification_monitor is not None,
                "broadcaster": self.broadcaster is not None,
                "knowledge_index": self.knowledge is not None,
                "runtime_monitor": self.monitor is not None,
                "memory": self.memory is not None,
                "command_bus": self.command_bus is not None,
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
        logger.info("=== Nex Agent shutting down ===")
        self.notification_monitor.stop()
        self.status = "offline"

    # ── Internal ────────────────────────────────────────────────

    def _handle_incoming_message(self, message) -> None:
        action = message.get("action", "") if isinstance(message, dict) else ""
        logger.info(f"Received message: {action}")

    def refresh_knowledge(self) -> None:
        if self.knowledge:
            self.knowledge.build_index()

    def handle_alert(self, severity: str, source: str, issue: str, context: Optional[Dict] = None) -> None:
        logger.warning(f"Alert [{severity}] from {source}: {issue}")

    def execute_command(self, target_agent: str, action: str, params: Optional[Dict] = None) -> None:
        if self.command_bus:
            self.command_bus.send(from_agent="nex_agent", to_agent=target_agent, action=action, params=params or {})


# ── Module-level convenience ────────────────────────────────────

_nex_agent: Optional[NexAgent] = None


def get_nex_agent(**kwargs) -> NexAgent:
    global _nex_agent
    if _nex_agent is None:
        _nex_agent = NexAgent.get_instance(**kwargs)
    return _nex_agent
