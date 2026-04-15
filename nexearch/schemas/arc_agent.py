"""
Nexearch — Arc Agent Schemas
Chat, tasks, tools, sub-agents, and modification schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Chat Schemas ──────────────────────────────────────────────

class ArcChatMessage(BaseModel):
    """A message sent to/from the Arc Agent."""
    content: str = ""
    role: str = "user"  # user, assistant, system
    client_id: Optional[str] = None  # Scope to specific client
    context: str = "general"
    # general, client, evolution, performance, publishing, scraping, writing


class ArcChatResponse(BaseModel):
    """Response from the Arc Agent."""
    id: str
    conversation_id: str
    content: str = ""
    role: str = "assistant"
    rich_type: Optional[str] = None
    rich_data: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    delegated_to_agent: Optional[str] = None
    created_at: Optional[datetime] = None


class ArcConversationResponse(BaseModel):
    """Response for a conversation."""
    id: str
    title: str = ""
    context: str = "general"
    client_id: Optional[str] = None
    message_count: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Task Schemas ──────────────────────────────────────────────

class ArcTaskCreate(BaseModel):
    """Create a new Arc Agent task."""
    task_name: str
    task_type: str
    client_id: Optional[str] = None
    is_global: bool = False
    priority: int = Field(default=5, ge=1, le=10)
    input_data: Dict[str, Any] = {}
    timeout_seconds: int = 3600
    scheduled_at: Optional[datetime] = None


class ArcTaskResponse(BaseModel):
    """Response for an Arc Agent task."""
    id: str
    task_name: str
    task_type: str
    client_id: Optional[str] = None
    status: str = "pending"
    assigned_agent: str = "arc"
    priority: int = 5
    progress: int = 0
    progress_message: str = ""
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Tool Schemas ──────────────────────────────────────────────

class ArcToolCreate(BaseModel):
    """Create a custom tool for Arc Agent."""
    tool_name: str
    tool_description: str
    tool_type: str
    implementation_code: str
    parameters_schema: Dict[str, Any] = {}
    return_schema: Dict[str, Any] = {}
    requires_approval: bool = False


class ArcToolResponse(BaseModel):
    """Response for an Arc Agent tool."""
    id: str
    tool_name: str
    tool_description: str
    tool_type: str
    is_active: bool = True
    requires_approval: bool = False
    usage_count: int = 0
    success_rate: float = 1.0
    version: str = "1.0"
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Sub-Agent Schemas ─────────────────────────────────────────

class ArcSubAgentCreate(BaseModel):
    """Create a new sub-agent under Arc."""
    agent_name: str
    agent_description: str
    agent_role: str
    system_prompt: str
    tools_available: List[str] = []
    skills_available: List[str] = []
    model_preference: str = ""
    client_scope: Optional[str] = None
    platform_scope: Optional[str] = None
    can_talk_to: List[str] = []


class ArcSubAgentResponse(BaseModel):
    """Response for a sub-agent."""
    id: str
    agent_name: str
    agent_description: str
    agent_role: str
    is_active: bool = True
    is_running: bool = False
    tasks_completed: int = 0
    tasks_failed: int = 0
    success_rate: float = 1.0
    can_talk_to: List[str] = []
    parent_agent: str = "arc"
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Modification Log Schemas ─────────────────────────────────

class ModificationLogResponse(BaseModel):
    """Response for a modification log entry."""
    id: str
    client_id: Optional[str] = None
    target_type: str
    target_field: Optional[str] = None
    change_reason: str
    modified_by: str
    sub_agent_name: Optional[str] = None
    is_reverted: bool = False
    is_revertable: bool = True
    feedback_type: Optional[str] = None
    modified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RevertModificationRequest(BaseModel):
    """Request to revert a modification."""
    modification_id: str
    reason: str = ""
    reverted_by: str = "admin"


class FeedbackRequest(BaseModel):
    """Submit feedback on a modification (positive/negative)."""
    modification_id: str
    feedback_type: str  # positive, negative, neutral
    feedback_note: str = ""


# ── Overview Schemas ──────────────────────────────────────────

class ArcAgentOverview(BaseModel):
    """Overview of Arc Agent's current state."""
    is_active: bool = True
    total_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_tools: int = 0
    total_sub_agents: int = 0
    active_sub_agents: int = 0
    total_modifications: int = 0
    pending_modifications: int = 0
    total_conversations: int = 0
    memory_stats: Dict[str, Any] = {}
