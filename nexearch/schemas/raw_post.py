"""
Nexearch — Raw Post Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class PostMetrics(BaseModel):
    """Engagement metrics for a post."""
    likes: int = 0
    comments: int = 0
    shares: Optional[int] = None
    saves: Optional[int] = None
    views: Optional[int] = None
    reach: Optional[int] = None
    impressions: Optional[int] = None
    profile_visits: Optional[int] = None
    link_clicks: Optional[int] = None
    replies: Optional[int] = None
    retweets: Optional[int] = None
    quotes: Optional[int] = None
    reactions: Optional[Dict[str, int]] = None  # FB/LinkedIn


class RawPostCreate(BaseModel):
    """Schema for creating a raw post record from scraping."""
    post_id: str
    platform: str
    account_id: str
    url: str
    format: str
    caption: str = ""
    title: str = ""
    description: str = ""
    hashtags: List[str] = []
    mentions: List[str] = []
    tags: List[str] = []
    transcript: str = ""
    audio_name: Optional[str] = None
    audio_is_original: Optional[bool] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    media_urls: List[str] = []
    duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    posted_at: Optional[datetime] = None
    day_of_week: Optional[str] = None
    hour_of_day: Optional[int] = None
    timezone_offset: Optional[str] = None
    metrics: PostMetrics = PostMetrics()
    follower_count_at_post: Optional[int] = None
    engagement_rate: float = 0.0
    scrape_method: str = ""
    raw_json: Optional[str] = None


class RawPostResponse(BaseModel):
    """Schema for raw post API responses."""
    id: str
    client_id: str
    post_id: str
    platform: str
    url: str
    format: str
    caption: str = ""
    title: str = ""
    transcript: str = ""
    hashtags: List[str] = []
    duration_seconds: Optional[float] = None
    posted_at: Optional[datetime] = None
    day_of_week: Optional[str] = None
    hour_of_day: Optional[int] = None
    likes: int = 0
    comments: int = 0
    shares: Optional[int] = None
    saves: Optional[int] = None
    views: Optional[int] = None
    engagement_rate: float = 0.0
    first_scraped_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RawPostListResponse(BaseModel):
    """Schema for listing raw posts."""
    posts: List[RawPostResponse]
    total: int
    page: int = 1
    per_page: int = 50
