"""
Nexearch — Account DNA Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class WinningPatterns(BaseModel):
    """Patterns that drive success for this account."""
    top_hook_types: List[str] = []
    top_content_categories: List[str] = []
    top_primary_topics: List[str] = []
    dominant_emotional_triggers: List[str] = []
    preferred_caption_length: str = ""
    cta_types_that_work: List[str] = []
    optimal_posting_hours: List[int] = []
    optimal_posting_days: List[str] = []
    format_performance_ranking: Dict[str, int] = {}
    audio_strategy: str = ""
    emoji_strategy: str = ""
    hashtag_strategy: str = ""
    writing_patterns: List[str] = []
    title_patterns: List[str] = []
    description_patterns: List[str] = []


class AvoidPatterns(BaseModel):
    """Patterns to avoid based on C-tier analysis."""
    weak_hook_types: List[str] = []
    underperforming_topics: List[str] = []
    poor_posting_times: List[int] = []
    c_tier_caption_patterns: List[str] = []
    c_tier_title_patterns: List[str] = []
    c_tier_description_patterns: List[str] = []
    summary: str = ""


class AudienceProfile(BaseModel):
    """Inferred audience characteristics."""
    inferred_audience_description: str = ""
    primary_desire: str = ""
    primary_fear_pain: str = ""
    content_consumption_style: str = ""
    identity_language: str = ""
    age_range_estimate: str = ""
    interests: List[str] = []
    engagement_preference: str = ""  # "comments", "shares", "saves", "likes"


class BaselineMetrics(BaseModel):
    """Account baseline performance metrics."""
    avg_engagement_rate: float = 0.0
    avg_views: Optional[float] = None
    avg_likes: float = 0.0
    avg_comments: float = 0.0
    avg_shares: Optional[float] = None
    avg_saves: Optional[float] = None
    top_post_engagement_rate: float = 0.0
    median_post_engagement_rate: float = 0.0
    posts_per_week: float = 0.0
    growth_rate_monthly: Optional[float] = None


class NexClipStyleRecommendation(BaseModel):
    """Recommendations for NexClip clip generation based on DNA."""
    recommended_clip_length_seconds: int = 38
    recommended_hook_style: str = ""
    recommended_caption_preset: str = ""
    recommended_pacing: str = ""
    recommended_topics: List[str] = []
    tone_descriptor: str = ""


class WritingDNA(BaseModel):
    """Writing style DNA for Nex Agent integration."""
    title_patterns: List[str] = []
    description_patterns: List[str] = []
    caption_patterns: List[str] = []
    vocabulary_style: str = ""
    sentence_structure: str = ""
    emoji_usage: str = ""
    power_words: List[str] = []
    opening_patterns: List[str] = []
    closing_patterns: List[str] = []
    cta_patterns: List[str] = []


class AccountDNASchema(BaseModel):
    """Complete Account DNA profile."""
    client_id: str
    account_handle: str
    platform: str
    generated_at: Optional[datetime] = None
    data_sample_size: int = 0

    winning_patterns: WinningPatterns = WinningPatterns()
    avoid_patterns: AvoidPatterns = AvoidPatterns()
    audience_profile: AudienceProfile = AudienceProfile()
    baseline_metrics: BaselineMetrics = BaselineMetrics()
    nexclip_style_recommendation: NexClipStyleRecommendation = NexClipStyleRecommendation()
    writing_dna: WritingDNA = WritingDNA()
    content_dna_summary: str = ""


class AccountDNAResponse(BaseModel):
    """API response for Account DNA."""
    id: str
    client_id: str
    account_handle: str
    platform: str
    data_sample_size: int = 0
    confidence_score: float = 0.0
    dna_version: str = ""
    content_dna_summary: str = ""
    s_tier_count: int = 0
    a_tier_count: int = 0
    b_tier_count: int = 0
    c_tier_count: int = 0
    avg_engagement_rate: float = 0.0
    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
