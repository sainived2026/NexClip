"""
Nexearch — Raw Post Model
Stores every scraped post from a client's social media account.
Supports upsert on post_id for re-scrape metric updates.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, Index, UniqueConstraint
)
from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NexearchRawPost(Base):
    """A single scraped social media post with all extractable signals."""
    __tablename__ = "nexearch_raw_posts"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)
    post_id = Column(String(500), nullable=False)  # Platform-native ID
    platform = Column(String(50), nullable=False)
    account_id = Column(String(500), nullable=False)
    url = Column(String(2000), nullable=False)

    # ── Content Format ────────────────────────────────────────
    format = Column(String(50), nullable=False)
    # reel, carousel, static_image, story, tiktok_video,
    # youtube_short, youtube_video, tweet, linkedin_video, linkedin_post,
    # facebook_video, facebook_post

    # ── Text Content ──────────────────────────────────────────
    caption = Column(Text, default="")
    title = Column(Text, default="")  # YouTube/Facebook video titles
    description = Column(Text, default="")  # YouTube descriptions
    hashtags = Column(Text, default="[]")  # JSON array
    mentions = Column(Text, default="[]")  # JSON array
    tags = Column(Text, default="[]")  # JSON array (topic/content tags)

    # ── Media ─────────────────────────────────────────────────
    audio_name = Column(String(500), nullable=True)
    audio_is_original = Column(Boolean, nullable=True)
    thumbnail_url = Column(String(2000), nullable=True)
    video_url = Column(String(2000), nullable=True)
    media_urls = Column(Text, default="[]")  # JSON array (carousel images etc.)
    duration_seconds = Column(Float, nullable=True)
    aspect_ratio = Column(String(20), nullable=True)  # "9:16", "16:9", "1:1"
    resolution = Column(String(20), nullable=True)  # "1080x1920"

    # ── Timing ────────────────────────────────────────────────
    posted_at = Column(DateTime, nullable=True)
    day_of_week = Column(String(20), nullable=True)
    hour_of_day = Column(Integer, nullable=True)
    timezone_offset = Column(String(10), nullable=True)

    # ── Engagement Metrics ────────────────────────────────────
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    views = Column(Integer, nullable=True)
    reach = Column(Integer, nullable=True)
    impressions = Column(Integer, nullable=True)
    profile_visits = Column(Integer, nullable=True)
    link_clicks = Column(Integer, nullable=True)
    replies = Column(Integer, nullable=True)  # Twitter/X replies
    retweets = Column(Integer, nullable=True)  # Twitter/X retweets
    quotes = Column(Integer, nullable=True)  # Twitter/X quote tweets
    reactions = Column(Text, nullable=True)  # JSON dict for Facebook/LinkedIn reactions

    # ── Computed ───────────────────────────────────────────────
    follower_count_at_post = Column(Integer, nullable=True)
    engagement_rate = Column(Float, default=0.0)

    # ── Scrape Metadata ───────────────────────────────────────
    scrape_method = Column(String(50), default="")  # apify, platform_api, crawlee_playwright
    raw_json = Column(Text, nullable=True)  # Full raw response for debugging
    raw_html = Column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    first_scraped_at = Column(DateTime, default=_utcnow)
    last_updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("client_id", "post_id", "platform", name="uq_client_post_platform"),
        Index("ix_nexearch_raw_posts_engagement", "client_id", "platform", "posted_at", "engagement_rate"),
        Index("ix_nexearch_raw_posts_format", "client_id", "format"),
    )
