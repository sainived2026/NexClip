"""
Nexearch — Client Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class PlatformEnum(str, Enum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    FACEBOOK = "facebook"


class ScrapingMethodEnum(str, Enum):
    APIFY = "apify"
    PLATFORM_API = "platform_api"
    CRAWLEE_PLAYWRIGHT = "crawlee_playwright"


class PublishingMethodEnum(str, Enum):
    METRICOOL = "metricool"
    PLATFORM_API = "platform_api"
    CRAWLEE_PLAYWRIGHT = "crawlee_playwright"


class ClientCreate(BaseModel):
    """Schema for registering a new client account."""
    account_url: str = Field(..., min_length=5, description="Full URL of the social media account")
    platform: PlatformEnum
    account_handle: str = Field(..., min_length=1, description="@handle of the account")
    display_name: str = ""

    # Scraping & Publishing
    scraping_method: ScrapingMethodEnum = ScrapingMethodEnum.APIFY
    publishing_method: PublishingMethodEnum = PublishingMethodEnum.METRICOOL

    # Metricool Integration
    metricool_brand_id: str = ""
    metricool_profile_id: str = ""

    # Platform API Credentials (optional)
    platform_access_token: str = ""
    platform_refresh_token: str = ""
    platform_page_id: str = ""

    # Session Credentials (for Crawlee/Playwright — JSON string)
    credentials_json: str = ""

    # Settings
    auto_publish_enabled: bool = False
    require_approval: bool = True
    rescrape_interval_hours: int = 24

    # Account Info
    primary_niche: str = ""
    secondary_niches: List[str] = []
    content_language: str = "en"


class ClientUpdate(BaseModel):
    """Schema for updating client settings."""
    display_name: Optional[str] = None
    scraping_method: Optional[ScrapingMethodEnum] = None
    publishing_method: Optional[PublishingMethodEnum] = None
    metricool_brand_id: Optional[str] = None
    metricool_profile_id: Optional[str] = None
    platform_access_token: Optional[str] = None
    platform_refresh_token: Optional[str] = None
    platform_page_id: Optional[str] = None
    credentials_json: Optional[str] = None
    auto_publish_enabled: Optional[bool] = None
    require_approval: Optional[bool] = None
    rescrape_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None
    is_paused: Optional[bool] = None
    primary_niche: Optional[str] = None
    secondary_niches: Optional[List[str]] = None
    content_language: Optional[str] = None


class ClientResponse(BaseModel):
    """Schema for client API responses."""
    id: str
    client_id: str
    account_url: str
    platform: str
    account_handle: str
    display_name: str = ""
    scraping_method: str
    publishing_method: str
    metricool_brand_id: str = ""
    metricool_profile_id: str = ""
    auto_publish_enabled: bool = False
    require_approval: bool = True
    rescrape_interval_hours: int = 24
    is_active: bool = True
    is_paused: bool = False
    total_posts_scraped: int = 0
    total_posts_analyzed: int = 0
    total_clips_published: int = 0
    last_scraped_at: Optional[datetime] = None
    last_analyzed_at: Optional[datetime] = None
    current_dna_version: str = ""
    dna_confidence_score: float = 0.0
    primary_niche: str = ""
    secondary_niches: List[str] = []
    content_language: str = "en"
    follower_count: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    """Schema for listing multiple clients."""
    clients: List[ClientResponse]
    total: int
