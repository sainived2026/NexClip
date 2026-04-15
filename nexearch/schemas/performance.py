"""
Nexearch — Performance & Clip Score Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class PollMetrics(BaseModel):
    """Metrics collected during a performance poll."""
    views: Optional[int] = None
    likes: int = 0
    comments: int = 0
    shares: Optional[int] = None
    saves: Optional[int] = None
    reach: Optional[int] = None
    impressions: Optional[int] = None
    profile_visits: Optional[int] = None
    link_clicks: Optional[int] = None
    replies: Optional[int] = None
    retweets: Optional[int] = None
    quotes: Optional[int] = None
    reactions: Optional[Dict[str, int]] = None


class ComputedMetrics(BaseModel):
    """Computed metrics from poll data."""
    engagement_rate: float = 0.0
    engagement_vs_baseline: float = 1.0
    views_vs_baseline: Optional[float] = None
    growth_rate_24h: Optional[float] = None
    velocity_score: Optional[float] = None


class PerformanceResultSchema(BaseModel):
    """Complete performance result for a poll window."""
    nexearch_publish_id: str
    poll_window: str  # "24h", "48h", "7d"
    polled_at: Optional[datetime] = None
    metrics: PollMetrics = PollMetrics()
    computed: ComputedMetrics = ComputedMetrics()
    platform: str = ""
    platform_metrics: Dict = {}
    data_source: str = ""


class PerformanceResultResponse(BaseModel):
    """API response for a performance result."""
    id: str
    nexearch_publish_id: str
    client_id: str
    poll_window: str
    polled_at: Optional[datetime] = None
    views: Optional[int] = None
    likes: int = 0
    comments: int = 0
    shares: Optional[int] = None
    saves: Optional[int] = None
    reach: Optional[int] = None
    engagement_rate: float = 0.0
    engagement_vs_baseline: float = 1.0
    views_vs_baseline: Optional[float] = None

    model_config = {"from_attributes": True}


class PublishedClipScoreSchema(BaseModel):
    """Score assigned to a published clip after performance measurement."""
    nexearch_publish_id: str
    clip_id: Optional[str] = None
    tier: str  # S, A, B, C
    total_score: float = 0.0
    vs_baseline: float = 1.0
    directive_effectiveness: float = 0.0
    performance_notes: str = ""
    improvement_suggestions: str = ""


class PerformanceReport(BaseModel):
    """Full performance report for a client."""
    client_id: str
    total_published: int = 0
    total_evaluated: int = 0
    tier_distribution: Dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0}
    avg_engagement_rate: float = 0.0
    avg_vs_baseline: float = 1.0
    best_performing_post: Optional[str] = None
    worst_performing_post: Optional[str] = None
    trending_up: bool = False
    roi_summary: str = ""
    results: List[PerformanceResultResponse] = []
