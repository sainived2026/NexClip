"""
Nexearch — Client Model
Represents a registered social media account being tracked by Nexearch.
Each client maps to one social media account on one platform.
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


class NexearchClient(Base):
    """A client account being analyzed and managed by Nexearch."""
    __tablename__ = "nexearch_clients"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)  # FK concept to NexClip users.id
    account_url = Column(String(2000), nullable=False)
    platform = Column(String(50), nullable=False)  # instagram, tiktok, youtube, twitter, linkedin, facebook
    account_handle = Column(String(500), nullable=False)
    display_name = Column(String(500), default="")

    # ── Metricool Integration ─────────────────────────────────
    metricool_brand_id = Column(String(100), default="")
    metricool_profile_id = Column(String(100), default="")

    # ── Scraping Method ───────────────────────────────────────
    # "apify" | "platform_api" | "crawlee_playwright"
    scraping_method = Column(String(50), default="apify")

    # ── Publishing Method ─────────────────────────────────────
    # "metricool" | "platform_api" | "crawlee_playwright"
    publishing_method = Column(String(50), default="metricool")

    # ── Platform API Credentials (encrypted at rest) ──────────
    platform_access_token = Column(Text, default="")  # Fernet-encrypted
    platform_refresh_token = Column(Text, default="")
    platform_token_expires_at = Column(DateTime, nullable=True)
    platform_page_id = Column(String(500), default="")  # e.g., Instagram Business Page ID

    # ── Session Credentials (for Crawlee/Playwright scraping) ─
    credentials_encrypted = Column(Text, default="")  # Fernet-encrypted JSON

    # ── Operational Settings ──────────────────────────────────
    auto_publish_enabled = Column(Boolean, default=False)
    require_approval = Column(Boolean, default=True)
    rescrape_interval_hours = Column(Integer, default=24)
    is_active = Column(Boolean, default=True)
    is_paused = Column(Boolean, default=False)

    # ── Tracking ──────────────────────────────────────────────
    total_posts_scraped = Column(Integer, default=0)
    total_posts_analyzed = Column(Integer, default=0)
    total_clips_published = Column(Integer, default=0)
    last_scraped_at = Column(DateTime, nullable=True)
    last_analyzed_at = Column(DateTime, nullable=True)
    last_published_at = Column(DateTime, nullable=True)
    last_scrape_cursor = Column(String(500), default="")  # Resume point for scraping

    # ── DNA & Directive ───────────────────────────────────────
    current_dna_version = Column(String(100), default="")
    current_directive_id = Column(String(100), default="")
    dna_confidence_score = Column(Float, default=0.0)

    # ── Niche & Category ──────────────────────────────────────
    primary_niche = Column(String(200), default="")
    secondary_niches = Column(Text, default="[]")  # JSON array
    content_language = Column(String(10), default="en")
    follower_count = Column(Integer, default=0)

    # ── Timestamps ────────────────────────────────────────────
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_nexearch_clients_platform_handle", "platform", "account_handle"),
        Index("ix_nexearch_clients_active", "is_active", "is_paused"),
    )
