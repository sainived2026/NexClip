"""
Nexearch — Evolution Log & Prompt Override Models
Tracks all rubric changes, pattern shifts, and prompt customizations.
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


class NexearchEvolutionLog(Base):
    """Log of every evolution cycle change — rubric updates, pattern shifts, weight adjustments."""
    __tablename__ = "nexearch_evolution_log"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)
    cycle_id = Column(String(100), nullable=False)

    # ── Source ────────────────────────────────────────────────
    source = Column(String(50), nullable=False)
    # "scrape" | "analysis" | "scoring" | "performance_feedback" |
    # "manual" | "arc_agent" | "nex_agent" | "global_evolution"

    # ── Change Details ────────────────────────────────────────
    changes_made = Column(Text, default="{}")  # JSON: what changed
    old_weights = Column(Text, default="{}")  # JSON: previous rubric weights
    new_weights = Column(Text, default="{}")  # JSON: new rubric weights
    pattern_shift_delta = Column(Text, default="{}")  # JSON: pattern changes

    # ── Impact Metrics ────────────────────────────────────────
    affected_dimensions = Column(Text, default="[]")  # JSON array of affected scoring dimensions
    magnitude = Column(Float, default=0.0)  # 0-1: how significant was this change
    change_reason = Column(Text, default="")  # Human-readable explanation
    auto_applied = Column(Boolean, default=True)  # False if manual/admin triggered

    # ── Revert Support ────────────────────────────────────────
    is_reverted = Column(Boolean, default=False)
    reverted_at = Column(DateTime, nullable=True)
    reverted_by = Column(String(100), nullable=True)  # "admin", "arc_agent"
    revert_reason = Column(Text, nullable=True)
    previous_state_snapshot = Column(Text, default="{}")  # Full state before this change

    # ── Arc Agent Feedback ────────────────────────────────────
    arc_agent_assessment = Column(Text, nullable=True)  # Arc Agent's analysis of this change
    feedback_sentiment = Column(String(20), nullable=True)  # "positive", "negative", "neutral"

    # ── Metadata ──────────────────────────────────────────────
    logged_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_nexearch_evolution_client", "client_id", "logged_at"),
        Index("ix_nexearch_evolution_source", "source", "logged_at"),
    )


class NexearchPromptOverride(Base):
    """Per-client prompt customizations injected into agent prompts."""
    __tablename__ = "nexearch_prompt_overrides"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)

    # ── Override Configuration ────────────────────────────────
    override_key = Column(String(200), nullable=False)
    # Keys: "scoring_context", "analysis_focus", "hook_emphasis",
    #        "caption_style", "topic_priority", "audience_context",
    #        "platform_tuning", "nex_agent_system_prompt",
    #        "arc_agent_system_prompt", "writing_style"

    override_value = Column(Text, nullable=False)
    override_description = Column(Text, default="")  # What this override does

    # ── Source & History ──────────────────────────────────────
    source = Column(String(50), nullable=False)  # "evolution_engine", "manual_admin", "arc_agent", "nex_agent"
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher = applied later (overrides lower)

    # ── Change Tracking ───────────────────────────────────────
    previous_value = Column(Text, nullable=True)  # For revert support
    changed_at = Column(DateTime, default=_utcnow)
    changed_by = Column(String(100), default="")

    # ── Revert Support ────────────────────────────────────────
    is_reverted = Column(Boolean, default=False)
    reverted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_nexearch_overrides_key", "client_id", "override_key", "is_active"),
    )
