"""
Nexearch — Published Post Model
Tracks all posts published via Nexearch (Metricool, Platform API, or Crawlee).
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


class NexearchPublishedPost(Base):
    """A clip published via Nexearch to a social media platform."""
    __tablename__ = "nexearch_published_posts"

    id = Column(String, primary_key=True, default=_uuid)
    nexearch_publish_id = Column(String(100), nullable=False, unique=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)
    clip_id = Column(String(100), nullable=True)  # NexClip clip ID
    platform = Column(String(50), nullable=False)

    # ── Publishing Method ─────────────────────────────────────
    publish_method = Column(String(50), nullable=False)  # "metricool", "platform_api", "crawlee_playwright"

    # ── External IDs ──────────────────────────────────────────
    metricool_post_id = Column(String(200), nullable=True)
    platform_post_id = Column(String(500), nullable=True)  # Native platform post ID
    platform_post_url = Column(String(2000), nullable=True)  # Direct link to live post

    # ── Content Published ─────────────────────────────────────
    caption_used = Column(Text, default="")
    title_used = Column(Text, default="")  # YouTube/Facebook title
    description_used = Column(Text, default="")  # YouTube/Facebook description
    hashtags_used = Column(Text, default="[]")  # JSON array
    video_url = Column(String(2000), nullable=True)  # Source video URL
    thumbnail_url = Column(String(2000), nullable=True)
    video_duration_seconds = Column(Float, nullable=True)

    # ── Writing Attribution ───────────────────────────────────
    title_written_by = Column(String(50), default="")  # "nex_agent", "arc_agent", "manual", "nexclip"
    caption_written_by = Column(String(50), default="")
    description_written_by = Column(String(50), default="")

    # ── Directive Traceability ────────────────────────────────
    directive_id = Column(String(100), nullable=True)
    dna_version = Column(String(100), nullable=True)

    # ── Scheduling ────────────────────────────────────────────
    scheduled_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    publish_status = Column(String(30), default="pending")
    # pending, approved, scheduled, publishing, published, failed, rejected

    # ── Approval Gate ─────────────────────────────────────────
    requires_approval = Column(Boolean, default=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)  # "admin", "arc_agent", "auto"
    rejection_reason = Column(Text, nullable=True)

    # ── Performance Polling Schedule ──────────────────────────
    scheduled_poll_24h = Column(DateTime, nullable=True)
    scheduled_poll_48h = Column(DateTime, nullable=True)
    scheduled_poll_7d = Column(DateTime, nullable=True)
    performance_status = Column(String(20), default="pending")
    # pending, polling, partial, complete

    # ── Error Tracking ────────────────────────────────────────
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # ── Timestamps ────────────────────────────────────────────
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_nexearch_published_status", "client_id", "publish_status"),
        Index("ix_nexearch_published_platform", "client_id", "platform", "published_at"),
    )
