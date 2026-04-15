"""
Nexearch — Clip Directive Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ClipParameters(BaseModel):
    """Parameters for clip generation."""
    target_length_seconds: int = 38
    min_length_seconds: int = 25
    max_length_seconds: int = 55
    pacing_style: str = "medium"
    preferred_format: str = "talking_head"


class HookDirective(BaseModel):
    """Directive for how clips should hook the audience."""
    required_hook_type: str = ""
    alternative_hook_types: List[str] = []
    hook_must_start_with: Optional[str] = None
    max_hook_duration_seconds: int = 4
    hook_rewrite_instruction: str = ""


class CaptionDirective(BaseModel):
    """Directive for caption generation."""
    preset_name: str = ""
    line_break_style: str = ""
    max_words_per_line: int = 8
    cta_append: Optional[str] = None
    hashtag_strategy: str = ""
    suggested_hashtags: List[str] = []
    caption_tone: str = ""


class ContentDirective(BaseModel):
    """Directive for content selection and focus."""
    prioritize_topics: List[str] = []
    avoid_topics: List[str] = []
    emotional_tone_target: str = ""
    audience_description: str = ""
    identity_language: str = ""


class AvoidDirective(BaseModel):
    """Directive for what to avoid."""
    avoid_hook_types: List[str] = []
    avoid_slow_intros_over_seconds: int = 3
    avoid_filler_heavy_segments: bool = True
    avoid_topics: List[str] = []
    avoid_caption_patterns: List[str] = []


class PublishSettings(BaseModel):
    """Publishing schedule and approval settings."""
    metricool_profile_id: str = ""
    preferred_publish_days: List[str] = []
    preferred_publish_hours: List[int] = []
    auto_publish_enabled: bool = False
    require_approval_before_publish: bool = True


class WritingDirectives(BaseModel):
    """Directives for Nex Agent writing (titles, captions, descriptions)."""
    title_directive: str = ""
    caption_directive: str = ""
    description_directive: str = ""
    hashtag_directive: str = ""
    tone_guide: str = ""
    vocabulary_guide: str = ""
    audience_persona: str = ""


class ClipDirectiveSchema(BaseModel):
    """Complete ClipDirective for NexClip consumption."""
    directive_id: str = ""
    client_id: str = ""
    account_handle: str = ""
    platform: str = ""
    generated_at: Optional[datetime] = None
    dna_version: str = ""
    confidence_score: float = 0.0
    data_basis: int = 0

    clip_parameters: ClipParameters = ClipParameters()
    hook_directive: HookDirective = HookDirective()
    caption_directive: CaptionDirective = CaptionDirective()
    content_directive: ContentDirective = ContentDirective()
    avoid_directive: AvoidDirective = AvoidDirective()
    publish_settings: PublishSettings = PublishSettings()
    writing_directives: WritingDirectives = WritingDirectives()

    nexclip_system_prompt_injection: str = ""


class ClipDirectiveResponse(BaseModel):
    """API response for a clip directive."""
    id: str
    directive_id: str
    client_id: str
    dna_version: str
    confidence_score: float = 0.0
    data_basis: int = 0
    is_active: bool = True
    is_overridden: bool = False
    nexclip_system_prompt_injection: str = ""
    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DirectiveOverrideRequest(BaseModel):
    """Request to manually override directive fields."""
    fields: dict = {}  # Field path -> new value
    reason: str = ""
    override_by: str = "admin"
