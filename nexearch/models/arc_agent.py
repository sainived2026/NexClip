"""
Nexearch — Arc Agent Models
The Arc Agent is the autonomous controller of Nexearch.
It manages sub-agents, creates tools, and communicates with Nex Agent.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, Index
)
from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArcAgentConversation(Base):
    """Conversation thread with the Arc Agent (admin chat interface)."""
    __tablename__ = "nexearch_arc_conversations"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String(500), default="")
    context = Column(String(50), default="general")
    # Context: "general", "client_{client_id}", "evolution", "performance", "publishing"
    client_id = Column(String, nullable=True, index=True)  # Scoped to specific client if set

    # ── State ─────────────────────────────────────────────────
    is_active = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)
    model_used = Column(String(200), default="")

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ArcAgentMessage(Base):
    """Individual message in an Arc Agent conversation."""
    __tablename__ = "nexearch_arc_messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system", "tool"
    content = Column(Text, nullable=False, default="")
    status = Column(String(20), default="complete")  # "streaming", "complete", "error"

    # ── Rich Content ──────────────────────────────────────────
    rich_type = Column(String(50), nullable=True)
    # "status_card", "alert", "evolution_report", "client_report",
    # "performance_chart", "directive_preview", "modification_preview"
    rich_data = Column(Text, nullable=True)  # JSON for rich rendering

    # ── Tool Calls ────────────────────────────────────────────
    tool_calls = Column(Text, nullable=True)  # JSON array of tool calls made
    tool_results = Column(Text, nullable=True)  # JSON array of tool results

    # ── Sub-Agent Delegation ──────────────────────────────────
    delegated_to_agent = Column(String(100), nullable=True)  # Sub-agent that handled this
    delegation_status = Column(String(20), nullable=True)  # "pending", "running", "complete", "failed"

    # ── Metadata ──────────────────────────────────────────────
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)
    token_count = Column(Integer, default=0)


class ArcAgentTask(Base):
    """Tasks being executed by Arc Agent or its sub-agents."""
    __tablename__ = "nexearch_arc_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    task_name = Column(String(500), nullable=False)
    task_type = Column(String(100), nullable=False)
    # "scrape", "analyze", "score", "evolve", "publish", "monitor",
    # "write_title", "write_caption", "write_description",
    # "modify_config", "create_tool", "research", "report"

    # ── Scope ─────────────────────────────────────────────────
    client_id = Column(String, nullable=True, index=True)
    is_global = Column(Boolean, default=False)  # True for universal evolution tasks

    # ── Execution ─────────────────────────────────────────────
    status = Column(String(30), default="pending")
    # "pending", "queued", "running", "paused", "completed", "failed", "cancelled"
    assigned_agent = Column(String(100), default="arc")  # "arc", "scrape_sub", "write_sub", etc.
    priority = Column(Integer, default=5)  # 1-10, higher = more urgent
    progress = Column(Integer, default=0)  # 0-100
    progress_message = Column(String(500), default="")

    # ── Input/Output ──────────────────────────────────────────
    input_data = Column(Text, default="{}")  # JSON
    output_data = Column(Text, default="{}")  # JSON
    error_message = Column(Text, nullable=True)

    # ── Scheduling ────────────────────────────────────────────
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    timeout_seconds = Column(Integer, default=3600)

    # ── Parent Task (for sub-tasks) ───────────────────────────
    parent_task_id = Column(String, nullable=True, index=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_arc_tasks_status", "status", "priority"),
        Index("ix_arc_tasks_type", "task_type", "client_id"),
    )


class ArcAgentTool(Base):
    """Custom tools created by Arc Agent for itself."""
    __tablename__ = "nexearch_arc_tools"

    id = Column(String, primary_key=True, default=_uuid)
    tool_name = Column(String(200), nullable=False, unique=True)
    tool_description = Column(Text, nullable=False)
    tool_type = Column(String(50), nullable=False)
    # "python_function", "api_call", "data_query", "file_operation",
    # "agent_delegation", "analysis", "scraping", "publishing"

    # ── Implementation ────────────────────────────────────────
    implementation_code = Column(Text, nullable=False)  # Python code as string
    parameters_schema = Column(Text, default="{}")  # JSON Schema for params
    return_schema = Column(Text, default="{}")  # JSON Schema for return value

    # ── Access Control ────────────────────────────────────────
    created_by = Column(String(50), default="arc_agent")  # "arc_agent", "admin"
    is_active = Column(Boolean, default=True)
    requires_approval = Column(Boolean, default=False)  # If True, admin must approve before use

    # ── Usage Stats ───────────────────────────────────────────
    usage_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)
    success_rate = Column(Float, default=1.0)  # 0-1: how often this tool succeeds

    # ── Metadata ──────────────────────────────────────────────
    version = Column(String(20), default="1.0")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ArcAgentSubAgent(Base):
    """Sub-agents created and managed by Arc Agent."""
    __tablename__ = "nexearch_arc_sub_agents"

    id = Column(String, primary_key=True, default=_uuid)
    agent_name = Column(String(200), nullable=False, unique=True)
    agent_description = Column(Text, nullable=False)
    agent_role = Column(String(100), nullable=False)
    # "scraper", "writer", "analyzer", "publisher", "monitor",
    # "researcher", "optimizer", "reporter", "custom"

    # ── Configuration ─────────────────────────────────────────
    system_prompt = Column(Text, nullable=False)
    tools_available = Column(Text, default="[]")  # JSON array of tool names
    skills_available = Column(Text, default="[]")  # JSON array of skill names from .agent/skills
    model_preference = Column(String(100), default="")  # Preferred LLM model (or empty for default chain)

    # ── Scope ─────────────────────────────────────────────────
    client_scope = Column(String, nullable=True)  # Specific client_id or null for global
    platform_scope = Column(String(50), nullable=True)  # Specific platform or null for all

    # ── State ─────────────────────────────────────────────────
    is_active = Column(Boolean, default=True)
    is_running = Column(Boolean, default=False)
    current_task_id = Column(String, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True)

    # ── Performance ───────────────────────────────────────────
    tasks_completed = Column(Integer, default=0)
    tasks_failed = Column(Integer, default=0)
    avg_task_duration_seconds = Column(Float, default=0.0)
    success_rate = Column(Float, default=1.0)

    # ── Communication ─────────────────────────────────────────
    can_talk_to = Column(Text, default="[]")  # JSON array of agent names this agent can communicate with
    parent_agent = Column(String(100), default="arc")  # "arc" or another sub-agent name

    # ── Metadata ──────────────────────────────────────────────
    created_by = Column(String(50), default="arc_agent")
    version = Column(String(20), default="1.0")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ArcAgentModificationLog(Base):
    """
    Log of all modifications made by Arc Agent to client configs,
    system prompts, directives, etc. Supports full revert.
    """
    __tablename__ = "nexearch_arc_modification_log"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=True, index=True)  # Null for global modifications

    # ── Modification Target ───────────────────────────────────
    target_type = Column(String(100), nullable=False)
    # "system_prompt", "scoring_rubric", "clip_directive", "writing_style",
    # "scraping_config", "publishing_config", "prompt_override",
    # "sub_agent_config", "tool_config", "nex_agent_config"
    target_id = Column(String, nullable=True)  # ID of the specific record modified
    target_field = Column(String(200), nullable=True)  # Specific field modified

    # ── Change Details ────────────────────────────────────────
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    change_reason = Column(Text, nullable=False)  # Why Arc Agent made this change
    change_evidence = Column(Text, default="{}")  # JSON: data that supports the change

    # ── Impact Assessment ─────────────────────────────────────
    expected_impact = Column(Text, default="")  # What Arc thinks will happen
    actual_impact = Column(Text, nullable=True)  # Measured after change applied
    impact_score = Column(Float, nullable=True)  # -1 to 1: negative=bad, positive=good

    # ── Agent Attribution ─────────────────────────────────────
    modified_by = Column(String(100), nullable=False)  # "arc_agent", "nex_agent", "admin"
    sub_agent_name = Column(String(100), nullable=True)  # If a sub-agent made the change

    # ── Revert Support ────────────────────────────────────────
    is_reverted = Column(Boolean, default=False)
    reverted_at = Column(DateTime, nullable=True)
    reverted_by = Column(String(100), nullable=True)
    revert_reason = Column(Text, nullable=True)
    is_revertable = Column(Boolean, default=True)

    # ── Feedback Loop ─────────────────────────────────────────
    feedback_type = Column(String(20), nullable=True)  # "positive", "negative", "neutral"
    feedback_note = Column(Text, nullable=True)

    # ── Metadata ──────────────────────────────────────────────
    modified_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_arc_mods_client", "client_id", "modified_at"),
        Index("ix_arc_mods_target", "target_type", "modified_at"),
        Index("ix_arc_mods_revert", "is_reverted", "is_revertable"),
    )
