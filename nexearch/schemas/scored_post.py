"""
Nexearch — Scored Post Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class DimensionScores(BaseModel):
    """Individual dimension scores from the 5-dimension rubric."""
    engagement: float = Field(default=0.0, ge=0, le=30, description="Max 30 pts")
    hook: float = Field(default=0.0, ge=0, le=25, description="Max 25 pts")
    virality: float = Field(default=0.0, ge=0, le=20, description="Max 20 pts")
    content_quality: float = Field(default=0.0, ge=0, le=15, description="Max 15 pts")
    audience_psychology: float = Field(default=0.0, ge=0, le=10, description="Max 10 pts")


class DimensionDetails(BaseModel):
    """Detailed breakdown of how each dimension was scored."""
    engagement_breakdown: str = ""
    hook_breakdown: str = ""
    virality_breakdown: str = ""
    content_quality_breakdown: str = ""
    psychology_breakdown: str = ""


class RAGContext(BaseModel):
    """RAG retrieval context used during scoring."""
    similar_post_ids: List[str] = []
    global_signal_ids: List[str] = []
    confidence_boost: float = 0.0
    used_rag: bool = False


class ScoredPostSchema(BaseModel):
    """Complete scored post with tier assignment."""
    post_id: str
    tier: str = Field(..., pattern=r"^[SABC]$")
    total_score: float = Field(default=0.0, ge=0, le=100)
    dimension_scores: DimensionScores = DimensionScores()
    dimension_details: DimensionDetails = DimensionDetails()
    rag_context: RAGContext = RAGContext()
    scoring_notes: str = ""
    is_learning_candidate: bool = False


class ScoredPostResponse(BaseModel):
    """API response for a scored post."""
    id: str
    post_id: str
    client_id: str
    tier: str
    total_score: float = 0.0
    engagement_score: float = 0.0
    hook_score: float = 0.0
    virality_score: float = 0.0
    content_quality_score: float = 0.0
    psychology_score: float = 0.0
    scoring_notes: str = ""
    is_learning_candidate: bool = False
    scored_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TierDistribution(BaseModel):
    """Distribution of posts across tiers."""
    S: int = 0
    A: int = 0
    B: int = 0
    C: int = 0
    total: int = 0


class ScoredPostListResponse(BaseModel):
    """API response for listing scored posts."""
    posts: List[ScoredPostResponse]
    tier_distribution: TierDistribution = TierDistribution()
    total: int = 0
