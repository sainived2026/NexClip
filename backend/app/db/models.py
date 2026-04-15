"""
NexClip — SQLAlchemy ORM Models
Designed for SQLite (dev) and PostgreSQL (prod) compatibility.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, Enum as SAEnum, Boolean
)
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────
class ProjectStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    TRANSCRIBING = "TRANSCRIBING"
    ANALYZING = "ANALYZING"
    GENERATING_CLIPS = "GENERATING_CLIPS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ── Users ────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    avatar_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


# ── Projects ─────────────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.UPLOADED)
    progress = Column(Integer, default=0)  # 0-100
    status_message = Column(String(500), default="")
    error_message = Column(Text, default="")
    clip_count = Column(Integer, default=10)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    client_id = Column(String(100), nullable=True)

    # Foreign keys
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="projects")
    video = relationship("Video", back_populates="project", uselist=False, cascade="all, delete-orphan")
    transcript = relationship("Transcript", back_populates="project", uselist=False, cascade="all, delete-orphan")
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan", order_by="Clip.rank")


# ── Videos ───────────────────────────────────────────────────────
class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, default=generate_uuid)
    original_filename = Column(String(500), default="")
    file_path = Column(String(1000), nullable=False)
    source_url = Column(String(2000), default="")
    source_type = Column(String(50), default="upload")  # "upload" | "youtube" | "url"
    duration_seconds = Column(Float, default=0.0)
    file_size_bytes = Column(Integer, default=0)
    mime_type = Column(String(100), default="")
    created_at = Column(DateTime, default=utcnow)

    # Foreign keys
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="video")


# ── Transcripts ──────────────────────────────────────────────────
class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String, primary_key=True, default=generate_uuid)
    file_path = Column(String(1000), nullable=False)
    language = Column(String(10), default="en")
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    # Foreign keys
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="transcript")


# ── Clips ────────────────────────────────────────────────────────
class Clip(Base):
    __tablename__ = "clips"

    id = Column(String, primary_key=True, default=generate_uuid)
    rank = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    viral_score = Column(Float, nullable=False)
    title_suggestion = Column(String(500), default="")
    hook_text = Column(String(1000), default="")
    reason = Column(Text, default="")
    file_path = Column(String(1000), default="")
    file_path_landscape = Column(String(1000), default="")
    thumbnail_path = Column(String(1000), default="")
    scores_json = Column(Text, default="{}")  # Detailed scoring breakdown stored as JSON string

    # ── SFCS v2 Metadata ─────────────────────────────────────────
    sfcs_version = Column(String(20), default="v2")
    sfcs_faces_detected = Column(Integer, default=0)
    sfcs_frames_with_speaker = Column(Integer, default=0)
    sfcs_fallback_frames = Column(Integer, default=0)

    # ── Caption Engine ────────────────────────────────────────────
    caption_style_id = Column(String(50), default="")
    caption_status = Column(String(20), default="none")  # none | processing | done | failed
    captioned_video_url = Column(String(1000), default="")
    captioned_video_url_landscape = Column(String(1000), default="")
    word_timestamps = Column(Text, default="[]")  # JSON array of {word, start, end}

    created_at = Column(DateTime, default=utcnow)

    # Foreign keys
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="clips")


# ── Nex Agent Conversations ─────────────────────────────────────
class NexConversation(Base):
    __tablename__ = "nex_conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False, default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    model_used = Column(String(200), nullable=False, default="")
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, nullable=False, default=0)

    # Relationships
    owner = relationship("User")
    messages = relationship("NexMessage", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="NexMessage.created_at")


# ── Nex Agent Messages ──────────────────────────────────────────
class NexMessage(Base):
    __tablename__ = "nex_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("nex_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)          # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False, default="")  # Incrementally updated during streaming
    status = Column(String(20), nullable=False, default="complete")  # 'streaming' | 'complete' | 'error'
    rich_type = Column(String(50), nullable=True)       # 'status_card' | 'alert' | 'file_ref' | null
    rich_data = Column(Text, nullable=True)             # JSON for rich response rendering
    tool_calls = Column(Text, nullable=True)            # JSON array of tool calls made
    error_detail = Column(Text, nullable=True)          # Error message if status = 'error'
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at = Column(DateTime, nullable=True)
    token_count = Column(Integer, default=0)

    # Relationships
    conversation = relationship("NexConversation", back_populates="messages")
