"""
Nexearch — Account DNA Model
Stores the extracted content DNA profile for each client account.
Maintains version history for evolution tracking.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Index
)
from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NexearchAccountDNA(Base):
    """Current content DNA profile for a client account."""
    __tablename__ = "nexearch_account_dna"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, unique=True, index=True)
    account_handle = Column(String(500), nullable=False)
    platform = Column(String(50), nullable=False)

    # ── Full DNA (JSON) ───────────────────────────────────────
    dna_json = Column(Text, nullable=False, default="{}")
    # Contains the complete AccountDNA schema:
    # winning_patterns{}, avoid_patterns{}, audience_profile{},
    # baseline_metrics{}, content_dna_summary, nexclip_style_recommendation{}

    # ── Denormalized Key Fields ───────────────────────────────
    data_sample_size = Column(Integer, default=0)
    confidence_score = Column(Float, default=0.0)

    # ── Winning Patterns Summary ──────────────────────────────
    top_hook_types = Column(Text, default="[]")  # JSON array
    top_content_categories = Column(Text, default="[]")
    top_topics = Column(Text, default="[]")
    dominant_emotional_triggers = Column(Text, default="[]")
    preferred_caption_length = Column(String(20), default="")
    format_performance_ranking = Column(Text, default="{}")  # JSON dict

    # ── Baseline Metrics ──────────────────────────────────────
    avg_engagement_rate = Column(Float, default=0.0)
    avg_views = Column(Float, nullable=True)
    avg_likes = Column(Float, default=0.0)
    avg_comments = Column(Float, default=0.0)
    avg_shares = Column(Float, nullable=True)
    avg_saves = Column(Float, nullable=True)
    top_post_engagement_rate = Column(Float, default=0.0)
    median_post_engagement_rate = Column(Float, default=0.0)

    # ── Tier Distribution ─────────────────────────────────────
    s_tier_count = Column(Integer, default=0)
    a_tier_count = Column(Integer, default=0)
    b_tier_count = Column(Integer, default=0)
    c_tier_count = Column(Integer, default=0)

    # ── NexClip Recommendations ───────────────────────────────
    recommended_clip_length = Column(Integer, nullable=True)
    recommended_hook_style = Column(String(200), default="")
    recommended_pacing = Column(String(50), default="")
    recommended_tone = Column(String(200), default="")
    content_dna_summary = Column(Text, default="")

    # ── Platform-Specific DNA ─────────────────────────────────
    platform_specific_dna = Column(Text, default="{}")
    # YouTube: SEO keywords, thumbnail style, description patterns
    # Twitter: thread style, engagement timing, hashtag patterns
    # LinkedIn: professional tone, industry topics
    # TikTok: trend usage, audio selection, editing pace
    # Instagram: grid style, story frequency, reel patterns
    # Facebook: share triggers, group targeting

    # ── Writing DNA (for Nex Agent) ───────────────────────────
    writing_dna_json = Column(Text, default="{}")
    # title_patterns, description_patterns, caption_patterns,
    # vocabulary_style, sentence_structure, emoji_usage

    # ── Versioning ────────────────────────────────────────────
    dna_version = Column(String(100), default="v1.0.0")
    generated_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class NexearchAccountDNAHistory(Base):
    """Version history of AccountDNA for evolution tracking."""
    __tablename__ = "nexearch_account_dna_history"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)
    dna_json = Column(Text, nullable=False, default="{}")
    dna_version = Column(String(100), nullable=False)
    generated_at = Column(DateTime, default=_utcnow)

    # ── Change Summary ────────────────────────────────────────
    change_summary = Column(Text, default="")  # Human-readable summary of what changed
    change_source = Column(String(50), default="auto")  # "auto", "manual", "arc_agent", "performance_feedback"
    delta_json = Column(Text, default="{}")  # Diff from previous version

    __table_args__ = (
        Index("ix_nexearch_dna_history", "client_id", "generated_at"),
    )
