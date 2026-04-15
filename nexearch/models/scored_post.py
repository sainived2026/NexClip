"""
Nexearch — Scored Post Model
Stores the multi-dimensional rubric scores and tier assignments.
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


class NexearchScoredPost(Base):
    """Scored post with S/A/B/C tier assignment from Agent 3."""
    __tablename__ = "nexearch_scored_posts"

    id = Column(String, primary_key=True, default=_uuid)
    post_id = Column(String(500), nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)

    # ── Tier & Score ──────────────────────────────────────────
    tier = Column(String(2), nullable=False)  # S, A, B, C
    total_score = Column(Float, nullable=False, default=0.0)

    # ── Dimension Scores ──────────────────────────────────────
    engagement_score = Column(Float, default=0.0)  # max 30
    hook_score = Column(Float, default=0.0)  # max 25
    virality_score = Column(Float, default=0.0)  # max 20
    content_quality_score = Column(Float, default=0.0)  # max 15
    psychology_score = Column(Float, default=0.0)  # max 10

    # ── Detailed Dimension Breakdown (JSON) ───────────────────
    dimension_details_json = Column(Text, default="{}")
    # Breakdown of how each dimension was calculated

    # ── RAG Context (from evolution engine) ───────────────────
    rag_similar_posts = Column(Text, default="[]")  # JSON: post_ids of similar past posts used for calibration
    rag_confidence_boost = Column(Float, default=0.0)  # How much RAG context changed the score
    used_rag_context = Column(Boolean, default=False)

    # ── Scoring Notes ─────────────────────────────────────────
    scoring_notes = Column(Text, default="")
    is_learning_candidate = Column(Boolean, default=False)

    # ── Platform Performance Context ──────────────────────────
    platform = Column(String(50), nullable=True)
    engagement_rate = Column(Float, default=0.0)
    engagement_vs_avg = Column(Float, default=1.0)  # Ratio vs account average

    # ── Metadata ──────────────────────────────────────────────
    scored_at = Column(DateTime, default=_utcnow)
    scoring_version = Column(String(20), default="1.0")
    scoring_rubric_version = Column(String(20), default="1.0")

    __table_args__ = (
        Index("ix_nexearch_scored_tier", "client_id", "tier", "total_score"),
        Index("ix_nexearch_scored_learning", "is_learning_candidate", "tier"),
    )
