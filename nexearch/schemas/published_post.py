"""
Nexearch — Published Post Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PublishWebhookPayload(BaseModel):
    """Webhook payload sent by NexClip when a clip is ready to publish."""
    clip_id: str
    client_id: str
    video_url: str
    caption: str = ""
    title: str = ""
    description: str = ""
    platform: str = ""
    directive_id: str = ""
    duration_seconds: float = 0.0
    thumbnail_url: str = ""


class PublishRequest(BaseModel):
    """Manual publish request."""
    client_id: str
    video_url: str
    caption: str = ""
    title: str = ""
    description: str = ""
    hashtags: List[str] = []
    platform: str = ""
    schedule_at: Optional[datetime] = None
    publish_method: str = "metricool"  # metricool, platform_api, crawlee_playwright


class PublishedPostResponse(BaseModel):
    """API response for a published post."""
    id: str
    nexearch_publish_id: str
    client_id: str
    clip_id: Optional[str] = None
    platform: str
    publish_method: str
    publish_status: str = "pending"
    caption_used: str = ""
    title_used: str = ""
    description_used: str = ""
    platform_post_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    requires_approval: bool = True
    approved_at: Optional[datetime] = None
    performance_status: str = "pending"
    error_message: Optional[str] = None
    title_written_by: str = ""
    caption_written_by: str = ""
    description_written_by: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PublishedPostListResponse(BaseModel):
    """List of published posts."""
    posts: List[PublishedPostResponse]
    total: int
    pending_approval: int = 0
