from app.captions.models import CaptionStyle

"""
18 Premium Caption Styles for NexClip.
Each style feeds both the ASS compositor AND the Pillow renderers.
Style IDs match their renderer filenames in renderers/.
"""

_REGISTRY = {
    # ── 01 Opus Classic ────────────────────────────────────────
    "opus_classic": CaptionStyle(
        style_id="opus_classic",
        display_name="Opus Classic",
        font_family="Montserrat-ExtraBold.ttf", font_size=58, font_weight="extrabold",
        font_color="#FFFFFF", primary_color="#000000", secondary_color="#FFFFFF",
        outline_color="#000000", outline_width=3,
        description="White stroked text, yellow highlight on active word",
        position="center", position_y_pct=0.72, uppercase=False,
        extra_params={
            "font_family": "extrabold",
            "active_color": "#000000",
            "inactive_color": "#FFFFFF",
            "highlight_color": "rgba(255,230,0,1.0)",
            "highlight_padding": 6,
            "stroke_width": 3,
            "stroke_fill": "#000000",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 02 Ghost Karaoke ───────────────────────────────────────
    "ghost_karaoke": CaptionStyle(
        style_id="ghost_karaoke",
        display_name="Ghost Karaoke",
        font_family="Montserrat-Bold.ttf", font_size=54, font_weight="bold",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.35)",
        description="Faded ghost words, solid white on active with subtle scale",
        position="center", position_y_pct=0.72, uppercase=False, scale_active=1.05,
        extra_params={
            "font_family": "bold",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.35)",
            "active_size_boost": 3,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 03 Cinematic Lower ─────────────────────────────────────
    "cinematic_lower": CaptionStyle(
        style_id="cinematic_lower",
        display_name="Cinematic Lower",
        font_family="PlayfairDisplay-Bold.ttf", font_size=48, font_weight="display",
        font_color="#F5E6C8", primary_color="#F5E6C8", secondary_color="rgba(220,220,220,0.45)",
        description="Elegant italic bottom, warm cream active — no bar",
        position="bottom", position_y_pct=0.88, uppercase=False,
        extra_params={
            "font_family": "display",
            "active_color": "#F5E6C8",
            "inactive_color": "rgba(220,220,220,0.45)",
            "italic": True,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 04 All-Caps Tracker ────────────────────────────────────
    "allcaps_tracker": CaptionStyle(
        style_id="allcaps_tracker",
        display_name="All-Caps Tracker",
        font_family="Montserrat-Black.ttf", font_size=52, font_weight="black",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.22)",
        description="Wide-spaced uppercase, ghost-to-solid tracking",
        position="center", position_y_pct=0.72, uppercase=True, letter_spacing=5,
        extra_params={
            "font_family": "black",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.22)",
            "uppercase": True,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 05 Underline Reveal ────────────────────────────────────
    "underline_reveal": CaptionStyle(
        style_id="underline_reveal",
        display_name="Underline Reveal",
        font_family="Montserrat-Bold.ttf", font_size=52, font_weight="bold",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.45)",
        description="Ghost words, white active with underline decoration",
        position="center", position_y_pct=0.72,
        extra_params={
            "font_family": "bold",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.45)",
            "underline_active": True,
            "underline_thickness": 4,
            "underline_offset": 4,
            "color_b": "#FFFFFF",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 06 Serif Story ─────────────────────────────────────────
    "serif_story": CaptionStyle(
        style_id="serif_story",
        display_name="Serif Story",
        font_family="PlayfairDisplay-Bold.ttf", font_size=50, font_weight="display",
        font_color="#F5E6C8", primary_color="#F5E6C8", secondary_color="rgba(255,255,255,0.4)",
        description="Italic serif, warm cream active with gentle scale",
        position="center", position_y_pct=0.72, scale_active=1.04,
        extra_params={
            "font_family": "display",
            "active_color": "#F5E6C8",
            "inactive_color": "rgba(255,255,255,0.4)",
            "active_size_boost": 2,
            "italic": True,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 07 MrBeast Bold ────────────────────────────────────────
    "mrbeast_bold": CaptionStyle(
        style_id="mrbeast_bold",
        display_name="MrBeast Bold",
        font_family="Montserrat-Black.ttf", font_size=62, font_weight="black",
        font_color="#FFFFFF", primary_color="#FF6B00", secondary_color="#FFFFFF",
        outline_color="#000000", outline_width=4,
        description="Giant uppercase with orange active, thick black stroke, scale 1.06",
        position="center", position_y_pct=0.72, uppercase=True, scale_active=1.06,
        extra_params={
            "font_family": "black",
            "active_color": "#FF6B00",
            "inactive_color": "#FFFFFF",
            "uppercase": True,
            "stroke_width": 4,
            "stroke_fill": "#000000",
            "active_size_boost": 4,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 08 LinkedIn Clean ──────────────────────────────────────
    "linkedin_clean": CaptionStyle(
        style_id="linkedin_clean",
        display_name="LinkedIn Clean",
        font_family="Montserrat-Bold.ttf", font_size=50, font_weight="bold",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.28)",
        description="Minimal professional, subtle ghost to white",
        position="center", position_y_pct=0.72,
        extra_params={
            "font_family": "bold",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.28)",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 09 Reels Standard ──────────────────────────────────────
    "reels_standard": CaptionStyle(
        style_id="reels_standard",
        display_name="Reels Standard",
        font_family="Montserrat-ExtraBold.ttf", font_size=56, font_weight="extrabold",
        font_color="#FFFFFF", primary_color="#00C2FF", secondary_color="#FFFFFF",
        outline_color="#000000", outline_width=3,
        description="White stroked, cyan active",
        position="center", position_y_pct=0.72,
        extra_params={
            "font_family": "extrabold",
            "active_color": "#00C2FF",
            "inactive_color": "#FFFFFF",
            "stroke_width": 3,
            "stroke_fill": "#000000",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 10 Prestige Serif ──────────────────────────────────────
    "prestige_serif": CaptionStyle(
        style_id="prestige_serif",
        display_name="Prestige Serif",
        font_family="PlayfairDisplay-Bold.ttf", font_size=52, font_weight="display",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.35)",
        description="Elegant italic serif with letter spacing and scale",
        position="center", position_y_pct=0.72, letter_spacing=2, scale_active=1.06,
        extra_params={
            "font_family": "display",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.35)",
            "active_size_boost": 3,
            "italic": True,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 11 Highlighter Mark ────────────────────────────────────
    "highlighter_mark": CaptionStyle(
        style_id="highlighter_mark",
        display_name="Highlighter Mark",
        font_family="Montserrat-ExtraBold.ttf", font_size=56, font_weight="extrabold",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.32)",
        description="Ghost text, yellow highlight rectangle behind active word",
        position="center", position_y_pct=0.72,
        extra_params={
            "font_family": "extrabold",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.32)",
            "highlight_color": "rgba(255,214,0,0.22)",
            "highlight_padding": 6,
            "highlight_radius": 4,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 12 Spaced Impact ───────────────────────────────────────
    "spaced_impact": CaptionStyle(
        style_id="spaced_impact",
        display_name="Spaced Impact",
        font_family="Montserrat-Black.ttf", font_size=52, font_weight="black",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.22)",
        description="Ultra-wide letter spacing, uppercase, clean reveal",
        position="center", position_y_pct=0.72, uppercase=True, letter_spacing=8,
        extra_params={
            "font_family": "black",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.22)",
            "uppercase": True,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 13 Ghost Pill ──────────────────────────────────────────
    "ghost_pill": CaptionStyle(
        style_id="ghost_pill",
        display_name="Ghost Pill",
        font_family="Montserrat-Bold.ttf", font_size=52, font_weight="bold",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.35)",
        description="Ghost words, capsule border appears on active word",
        position="center", position_y_pct=0.72,
        extra_params={
            "font_family": "bold",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.35)",
            "pill_border": True,
            "pill_border_color": "rgba(255,255,255,0.85)",
            "pill_border_width": 2,
            "pill_radius": 30,
            "pill_padding_x": 18,
            "pill_padding_y": 6,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 14 Documentary Tag ─────────────────────────────────────
    "documentary_tag": CaptionStyle(
        style_id="documentary_tag",
        display_name="Documentary Tag",
        font_family="PlayfairDisplay-Bold.ttf", font_size=48, font_weight="display",
        font_color="#F5E6C8", primary_color="#F5E6C8", secondary_color="rgba(255,255,255,0.4)",
        description="Bottom-left tagged with TRANSCRIPT label + white rule line",
        position="bottom", position_y_pct=0.88,
        extra_params={
            "font_family": "display",
            "active_color": "#F5E6C8",
            "inactive_color": "rgba(255,255,255,0.4)",
            "italic": True,
            "tag_label": True,
            "tag_label_text": "TRANSCRIPT",
            "tag_rule_line": True,
            "align": "left",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 15 Feather Light ───────────────────────────────────────
    "feather_light": CaptionStyle(
        style_id="feather_light",
        display_name="Feather Light",
        font_family="NunitoSans-Regular.ttf", font_size=50, font_weight="regular",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.32)",
        description="Light font, weight shift only — no decoration",
        position="center", position_y_pct=0.72, letter_spacing=1,
        extra_params={
            "font_family": "regular",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.32)",
            "active_weight": "extrabold",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 16 Stroked Uppercase ───────────────────────────────────
    "stroked_uppercase": CaptionStyle(
        style_id="stroked_uppercase",
        display_name="Stroked Uppercase",
        font_family="Montserrat-Black.ttf", font_size=58, font_weight="black",
        font_color="#FFFFFF", primary_color="#FF3CAC", secondary_color="#FFFFFF",
        outline_color="#000000", outline_width=3,
        description="White stroked uppercase, pink active color",
        position="center", position_y_pct=0.72, uppercase=True,
        extra_params={
            "font_family": "black",
            "active_color": "#FF3CAC",
            "inactive_color": "#FFFFFF",
            "uppercase": True,
            "stroke_width": 3,
            "stroke_fill": "#000000",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 17 Accent Line ─────────────────────────────────────────
    "accent_line": CaptionStyle(
        style_id="accent_line",
        display_name="Accent Line",
        font_family="Montserrat-Bold.ttf", font_size=52, font_weight="bold",
        font_color="#FFFFFF", primary_color="#FFFFFF", secondary_color="rgba(255,255,255,0.35)",
        description="Ghost words, white active with thin bottom underline",
        position="center", position_y_pct=0.72,
        extra_params={
            "font_family": "bold",
            "active_color": "#FFFFFF",
            "inactive_color": "rgba(255,255,255,0.35)",
            "underline_active": True,
            "underline_thickness": 4,
            "underline_offset": 4,
            "color_b": "#FFFFFF",
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
    # ── 18 Warm Serif Glow ─────────────────────────────────────
    "warm_serif_glow": CaptionStyle(
        style_id="warm_serif_glow",
        display_name="Warm Serif Glow",
        font_family="PlayfairDisplay-Bold.ttf", font_size=54, font_weight="display",
        font_color="#F5E0B0", primary_color="#F5E0B0", secondary_color="rgba(255,255,255,0.32)",
        description="Italic serif with warm cream glow and generous scale",
        position="center", position_y_pct=0.72, letter_spacing=1, scale_active=1.08,
        extra_params={
            "font_family": "display",
            "active_color": "#F5E0B0",
            "inactive_color": "rgba(255,255,255,0.32)",
            "active_size_boost": 4,
            "italic": True,
            "shadow_offset": 0, "shadow_alpha": 0,
        },
    ),
}

def get_style(style_id: str) -> CaptionStyle:
    return _REGISTRY.get(style_id, _REGISTRY["opus_classic"])

def get_all_styles() -> list[CaptionStyle]:
    return list(_REGISTRY.values())
