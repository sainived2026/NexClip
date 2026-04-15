"""
NexClip — Caption Data Models
Complete data structures for the caption pipeline including
word timestamps, segments, and style configuration.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class CaptionWord:
    word: str
    start_ms: int
    end_ms: int
    confidence: float = 1.0

@dataclass
class CaptionSegment:
    words: List[CaptionWord]
    segment_start_ms: int
    segment_end_ms: int
    text: str

@dataclass
class CaptionStyle:
    """
    Full caption style definition used by both:
    - ASS compositor (FFmpeg subtitle burn)
    - Pillow renderers (per-frame overlay compositing)
    """
    style_id: str
    display_name: str
    # ── Font ──
    font_family: str = "Montserrat-ExtraBold.ttf"
    font_size: int = 52
    font_weight: str = "extrabold"        # key into _FONT_MAP: bold|extrabold|black|regular|display|mono
    font_color: str = "#FFFFFF"
    # ── Metadata ──
    description: str = ""
    # ── Colors ──
    primary_color: str = "#FFFFFF"        # active word color
    secondary_color: str = "#FFFFFF"      # inactive word color (for renderers that use it)
    bg_color: str = "none"                # background behind entire phrase
    outline_color: str = "#000000"
    outline_width: int = 0
    # ── Rendering control ──
    position: str = "center"              # center | bottom | bottom-left
    position_y_pct: float = 0.72          # vertical position as fraction of height
    uppercase: bool = False
    letter_spacing: int = 0
    scale_active: float = 1.0             # scale factor for active word
    word_by_word: bool = True             # word-by-word karaoke highlighting
    glow: bool = False                    # enable glow effect on active word
    # ── Extra parameters for renderers ──
    extra_params: Dict[str, Any] = field(default_factory=dict)
    # Common extra_params keys:
    #   active_color        — active word color override (rgba or hex)
    #   inactive_color      — inactive word color (rgba or hex)
    #   inactive_opacity    — inactive opacity (0.0-1.0)
    #   highlight_color     — highlight rectangle color behind active
    #   highlight_padding   — padding for highlight rectangle
    #   active_size_boost   — font size boost on active word (px)
    #   active_bg           — pill/capsule background for active word
    #   bubble_padding      — padding for active bg capsule
    #   underline_active    — draw underline on active word
    #   underline_thickness — underline thickness (px)
    #   stroke_width        — per-word stroke width
    #   font_family         — override font family key for resolving
    #   shadow_offset       — shadow offset (px)
    #   shadow_alpha        — shadow alpha 0-255
    #   shadow_color        — shadow color
    #   wave_color          — wave/underline color
    #   wave_thickness      — wave/underline thickness
    #   typewriter_cursor   — show blinking cursor
    #   uppercase           — uppercase override
