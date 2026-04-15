"""
NexClip — Caption Engine Configuration
All tunable parameters for the Multi-Style Caption Engine.
"""

CAPTION_CONFIG = {
    # Word grouping
    "words_per_segment": 4,

    # Output settings
    "default_width": 1080,
    "default_height": 1920,

    # Default style
    "default_style_id": "CLEAN_MINIMAL",

    # Preview thumbnail generation
    "preview_width": 360,
    "preview_height": 640,
    "preview_bg_color": "#1a1a2e",

    # Performance
    "max_concurrent_renders": 2,
    "render_timeout_seconds": 600,
}
