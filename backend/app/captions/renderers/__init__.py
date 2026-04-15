"""
NexClip — Caption Renderers Package
18 premium Pillow-based word-by-word karaoke caption renderers.
"""

from app.captions.renderers.base_renderer import BaseCaptionRenderer, ImageMagickCaptionRenderer

# ── 18 Named Renderers ──────────────────────────────────────────
from app.captions.renderers.opus_classic import OpusClassicRenderer
from app.captions.renderers.ghost_karaoke import GhostKaraokeRenderer
from app.captions.renderers.cinematic_lower import CinematicLowerRenderer
from app.captions.renderers.allcaps_tracker import AllCapsTrackerRenderer
from app.captions.renderers.underline_reveal import UnderlineRevealRenderer
from app.captions.renderers.serif_story import SerifStoryRenderer
from app.captions.renderers.mrbeast_bold import MrBeastBoldRenderer
from app.captions.renderers.linkedin_clean import LinkedInCleanRenderer
from app.captions.renderers.reels_standard import ReelsStandardRenderer
from app.captions.renderers.prestige_serif import PrestigeSerifRenderer
from app.captions.renderers.highlighter_mark import HighlighterMarkRenderer
from app.captions.renderers.spaced_impact import SpacedImpactRenderer
from app.captions.renderers.ghost_pill import GhostPillRenderer
from app.captions.renderers.documentary_tag import DocumentaryTagRenderer
from app.captions.renderers.feather_light import FeatherLightRenderer
from app.captions.renderers.stroked_uppercase import StrokedUppercaseRenderer
from app.captions.renderers.accent_line import AccentLineRenderer
from app.captions.renderers.warm_serif_glow import WarmSerifGlowRenderer

# ── Renderer Factory ─────────────────────────────────────────────
RENDERER_MAP = {
    "opus_classic": OpusClassicRenderer,
    "ghost_karaoke": GhostKaraokeRenderer,
    "cinematic_lower": CinematicLowerRenderer,
    "allcaps_tracker": AllCapsTrackerRenderer,
    "underline_reveal": UnderlineRevealRenderer,
    "serif_story": SerifStoryRenderer,
    "mrbeast_bold": MrBeastBoldRenderer,
    "linkedin_clean": LinkedInCleanRenderer,
    "reels_standard": ReelsStandardRenderer,
    "prestige_serif": PrestigeSerifRenderer,
    "highlighter_mark": HighlighterMarkRenderer,
    "spaced_impact": SpacedImpactRenderer,
    "ghost_pill": GhostPillRenderer,
    "documentary_tag": DocumentaryTagRenderer,
    "feather_light": FeatherLightRenderer,
    "stroked_uppercase": StrokedUppercaseRenderer,
    "accent_line": AccentLineRenderer,
    "warm_serif_glow": WarmSerifGlowRenderer,
}


def get_renderer(style_id: str, style, width: int = 1080, height: int = 1920) -> BaseCaptionRenderer:
    """
    Factory: get a renderer by style_id.
    Falls back to OpusClassicRenderer if style_id is unknown.
    """
    renderer_cls = RENDERER_MAP.get(style_id, OpusClassicRenderer)
    return renderer_cls(style, width, height)


__all__ = [
    "BaseCaptionRenderer", "ImageMagickCaptionRenderer",
    "RENDERER_MAP", "get_renderer",
    "OpusClassicRenderer", "GhostKaraokeRenderer", "CinematicLowerRenderer",
    "AllCapsTrackerRenderer", "UnderlineRevealRenderer", "SerifStoryRenderer",
    "MrBeastBoldRenderer", "LinkedInCleanRenderer", "ReelsStandardRenderer",
    "PrestigeSerifRenderer", "HighlighterMarkRenderer", "SpacedImpactRenderer",
    "GhostPillRenderer", "DocumentaryTagRenderer", "FeatherLightRenderer",
    "StrokedUppercaseRenderer", "AccentLineRenderer", "WarmSerifGlowRenderer",
]
