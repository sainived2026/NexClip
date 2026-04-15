"""
NexClip — Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# ── Auth ─────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = ""


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str
    avatar_url: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Projects ─────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    clip_count: Optional[int] = Field(10, ge=1, le=50)
    client_id: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    progress: int
    status_message: str
    error_message: Optional[str] = None
    clip_count: int
    created_at: datetime
    updated_at: datetime
    owner_id: str
    client_id: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    video: Optional["VideoResponse"] = None
    clips: List["ClipResponse"] = []

    model_config = {"from_attributes": True}


# ── Videos ───────────────────────────────────────────────────────

class VideoURLRequest(BaseModel):
    url: str = Field(..., min_length=5)
    title: Optional[str] = ""
    clip_count: Optional[int] = Field(10, ge=1, le=50)
    client_id: Optional[str] = None


class VideoResponse(BaseModel):
    id: str
    original_filename: str
    source_url: str
    source_type: str
    duration_seconds: float
    file_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Clips ────────────────────────────────────────────────────────

class ClipResponse(BaseModel):
    id: str
    rank: int
    start_time: float
    end_time: float
    duration: float
    viral_score: float
    title_suggestion: str
    hook_text: str
    reason: str
    file_path: str
    file_path_landscape: str = ""
    scores_json: str
    # SFCS v2
    sfcs_version: str = "v2"
    sfcs_faces_detected: int = 0
    sfcs_frames_with_speaker: int = 0
    sfcs_fallback_frames: int = 0
    # Captions
    caption_style_id: str = ""
    caption_status: str = "none"
    captioned_video_url: str = ""
    captioned_video_url_landscape: str = ""
    word_timestamps: str = "[]"
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipDownloadResponse(BaseModel):
    clip_id: str
    download_url: str
    title: str
    viral_score: float


# ── Captions ─────────────────────────────────────────────────────

class CaptionStyleResponse(BaseModel):
    style_id: str
    display_name: str
    font_size: int
    word_by_word: bool
    glow: bool


class ApplyCaptionRequest(BaseModel):
    style_id: str
    active_aspect: str = "9:16"


class CaptionStatusResponse(BaseModel):
    clip_id: str
    caption_status: str
    caption_style_id: str
    captioned_video_url: str
    captioned_video_url_landscape: str = ""


# ── Status ───────────────────────────────────────────────────────

class ProjectStatusResponse(BaseModel):
    project_id: str
    status: str
    progress: int
    status_message: str
    error_message: Optional[str] = None
