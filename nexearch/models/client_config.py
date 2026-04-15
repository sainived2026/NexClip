"""
Nexearch — Client Config & Writing Profile Models
Per-client configuration for NexClip system prompt overrides,
scraping preferences, and Nex Agent writing directives.
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


class NexearchClientConfig(Base):
    """
    Per-client configuration that Arc Agent + Nex Agent can modify.
    Stored separately from NexearchClient for clean separation of
    operational settings vs. AI-tuned behavior.
    """
    __tablename__ = "nexearch_client_configs"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)

    # ── NexClip System Prompt Override ─────────────────────────
    # This is what gets injected into NexClip's AI pipeline for this client
    nexclip_system_prompt = Column(Text, default="")
    nexclip_system_prompt_version = Column(String(50), default="v1.0")

    # ── Clip Generation Preferences ───────────────────────────
    preferred_clip_min_seconds = Column(Integer, default=25)
    preferred_clip_max_seconds = Column(Integer, default=55)
    preferred_clip_count = Column(Integer, default=10)
    preferred_pacing = Column(String(50), default="medium")  # fast_cut, medium, slow_build
    preferred_format = Column(String(50), default="reel")
    preferred_aspect_ratio = Column(String(20), default="9:16")

    # ── Content Preferences ───────────────────────────────────
    target_topics = Column(Text, default="[]")  # JSON array of preferred topics
    avoid_topics = Column(Text, default="[]")
    target_emotions = Column(Text, default="[]")  # JSON array of preferred emotional triggers
    brand_voice = Column(Text, default="")  # Description of client's brand voice
    tone_descriptor = Column(String(200), default="")  # e.g. "energetic + direct"

    # ── Platform-Specific Settings ────────────────────────────
    instagram_settings = Column(Text, default="{}")
    tiktok_settings = Column(Text, default="{}")
    youtube_settings = Column(Text, default="{}")
    twitter_settings = Column(Text, default="{}")
    linkedin_settings = Column(Text, default="{}")
    facebook_settings = Column(Text, default="{}")

    # ── Automated Behavior ────────────────────────────────────
    auto_evolve_enabled = Column(Boolean, default=True)
    auto_publish_enabled = Column(Boolean, default=False)
    auto_write_titles = Column(Boolean, default=True)
    auto_write_captions = Column(Boolean, default=True)
    auto_write_descriptions = Column(Boolean, default=True)
    auto_hashtag_generation = Column(Boolean, default=True)

    # ── Evolution Sensitivity ─────────────────────────────────
    evolution_aggressiveness = Column(Float, default=0.5)  # 0-1: how fast to adapt
    min_data_for_evolution = Column(Integer, default=10)  # Min posts before evolving
    max_evolution_delta = Column(Float, default=0.15)  # Max 15% change per cycle

    # ── Arc Agent Permissions for this client ─────────────────
    arc_can_modify_system_prompt = Column(Boolean, default=True)
    arc_can_modify_clip_prefs = Column(Boolean, default=True)
    arc_can_modify_writing = Column(Boolean, default=True)
    arc_can_auto_publish = Column(Boolean, default=False)

    # ── Metadata ──────────────────────────────────────────────
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_evolved_at = Column(DateTime, nullable=True)
    last_evolved_by = Column(String(100), nullable=True)


class NexearchClientWritingProfile(Base):
    """
    Per-client, per-platform writing profile for Nex Agent.
    Defines exactly how titles, captions, and descriptions should be written.
    Arc Agent updates this based on performance data.
    """
    __tablename__ = "nexearch_client_writing_profiles"

    id = Column(String, primary_key=True, default=_uuid)
    client_id = Column(String, nullable=False, index=True)
    platform = Column(String(50), nullable=False)
    # instagram, tiktok, youtube, twitter, linkedin, facebook

    # ── Title Writing ─────────────────────────────────────────
    title_system_prompt = Column(Text, default="")  # LLM system prompt for title generation
    title_examples = Column(Text, default="[]")  # JSON array of S-tier title examples
    title_max_length = Column(Integer, default=100)
    title_style = Column(String(100), default="")  # "click-bait", "informative", "emotional", etc.
    title_patterns = Column(Text, default="[]")  # JSON: winning title patterns
    title_avoid_patterns = Column(Text, default="[]")  # JSON: patterns to avoid

    # ── Caption Writing ───────────────────────────────────────
    caption_system_prompt = Column(Text, default="")
    caption_examples = Column(Text, default="[]")
    caption_max_length = Column(Integer, default=2200)  # Instagram max
    caption_style = Column(String(100), default="")
    caption_patterns = Column(Text, default="[]")
    caption_avoid_patterns = Column(Text, default="[]")
    caption_emoji_usage = Column(String(50), default="moderate")  # none, light, moderate, heavy
    caption_line_break_style = Column(String(50), default="")
    caption_cta_style = Column(String(200), default="")
    caption_hashtag_count = Column(Integer, default=15)

    # ── Description Writing (YouTube, Facebook, LinkedIn) ─────
    description_system_prompt = Column(Text, default="")
    description_examples = Column(Text, default="[]")
    description_max_length = Column(Integer, default=5000)
    description_style = Column(String(100), default="")
    description_patterns = Column(Text, default="[]")
    description_avoid_patterns = Column(Text, default="[]")
    description_seo_keywords = Column(Text, default="[]")  # JSON array
    description_include_links = Column(Boolean, default=True)
    description_include_timestamps = Column(Boolean, default=True)  # YouTube chapters

    # ── Hashtag Strategy ──────────────────────────────────────
    hashtag_system_prompt = Column(Text, default="")
    hashtag_pool = Column(Text, default="[]")  # JSON: curated hashtag pool
    hashtag_strategy = Column(String(50), default="mixed")  # none, niche_only, broad_only, mixed

    # ── Audience Context ──────────────────────────────────────
    audience_description = Column(Text, default="")
    audience_language_style = Column(Text, default="")
    identity_language = Column(Text, default="")

    # ── Performance Tracking ──────────────────────────────────
    avg_title_performance = Column(Float, default=0.0)
    avg_caption_performance = Column(Float, default=0.0)
    avg_description_performance = Column(Float, default=0.0)
    total_posts_written = Column(Integer, default=0)

    # ── Version & History ─────────────────────────────────────
    profile_version = Column(String(50), default="v1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    last_evolved_at = Column(DateTime, nullable=True)
    last_evolved_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_writing_profile", "client_id", "platform", "is_active"),
    )
