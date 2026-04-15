"""
Nexearch — Performance Result & Published Clip Score Models
Tracks post-publish performance data and scores published clips.
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


class NexearchPerformanceResult(Base):
    """Performance data polled at specific time windows after publishing."""
    __tablename__ = "nexearch_performance_results"

    id = Column(String, primary_key=True, default=_uuid)
    nexearch_publish_id = Column(String(100), nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)
    poll_window = Column(String(10), nullable=False)  # "24h", "48h", "7d"
    polled_at = Column(DateTime, default=_utcnow)

    # ── Raw Metrics ───────────────────────────────────────────
    views = Column(Integer, nullable=True)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    reach = Column(Integer, nullable=True)
    impressions = Column(Integer, nullable=True)
    profile_visits = Column(Integer, nullable=True)
    link_clicks = Column(Integer, nullable=True)
    replies = Column(Integer, nullable=True)
    retweets = Column(Integer, nullable=True)
    quotes = Column(Integer, nullable=True)
    reactions_json = Column(Text, nullable=True)  # JSON dict for FB/LinkedIn

    # ── Computed Metrics ──────────────────────────────────────
    engagement_rate = Column(Float, default=0.0)
    engagement_vs_baseline = Column(Float, default=1.0)  # ratio: 1.0 = matches baseline
    views_vs_baseline = Column(Float, nullable=True)
    growth_rate_24h = Column(Float, nullable=True)  # Metric growth rate in first 24h
    velocity_score = Column(Float, nullable=True)  # How fast engagement is growing

    # ── Platform-Specific Metrics ─────────────────────────────
    platform = Column(String(50), nullable=True)
    platform_metrics_json = Column(Text, default="{}")
    # YouTube: watch time, click-through rate, retention curve
    # Twitter: impression breakdown, engagement by type
    # LinkedIn: company page reach, job applicant clicks
    # TikTok: completion rate, loop count, share to other platforms
    # Instagram: story exits, reel replays, explore page reach
    # Facebook: organic vs paid reach, share chain depth

    # ── Data Source ───────────────────────────────────────────
    data_source = Column(String(50), default="")  # "metricool", "platform_api", "crawlee"

    __table_args__ = (
        Index("ix_nexearch_perf_window", "nexearch_publish_id", "poll_window"),
        Index("ix_nexearch_perf_client", "client_id", "polled_at"),
    )


class NexearchPublishedClipScore(Base):
    """Score assigned to a published clip after 7-day performance window."""
    __tablename__ = "nexearch_published_clip_scores"

    id = Column(String, primary_key=True, default=_uuid)
    nexearch_publish_id = Column(String(100), nullable=False, index=True)
    client_id = Column(String, nullable=False, index=True)
    clip_id = Column(String(100), nullable=True)

    # ── Scoring ───────────────────────────────────────────────
    tier = Column(String(2), nullable=False)  # S, A, B, C
    total_score = Column(Float, nullable=False, default=0.0)
    vs_baseline = Column(Float, default=1.0)  # engagement_rate / account_avg
    directive_effectiveness = Column(Float, default=0.0)  # 0-1: did the directive help?

    # ── Dimension Scores ──────────────────────────────────────
    engagement_score = Column(Float, default=0.0)
    virality_score = Column(Float, default=0.0)
    audience_response_score = Column(Float, default=0.0)
    content_fit_score = Column(Float, default=0.0)

    # ── Notes & Feedback ──────────────────────────────────────
    performance_notes = Column(Text, default="")
    improvement_suggestions = Column(Text, default="")  # What to do differently next time
    fed_back_to_evolution = Column(Integer, default=0)  # Boolean: has this been sent to Agent 4?

    # ── Metadata ──────────────────────────────────────────────
    platform = Column(String(50), nullable=True)
    scored_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_nexearch_clip_scores_tier", "client_id", "tier"),
    )
