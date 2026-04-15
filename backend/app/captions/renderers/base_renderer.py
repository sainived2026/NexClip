"""
NexClip — Base Caption Renderer (Pillow/PIL Edition)
Premium text rendering using Pillow ImageDraw + ImageFont.
Supports per-style font families, glow, highlight boxes, underlines,
size boosts, and all 18 unique visual effects.
"""

import os
import logging
from abc import ABC
from typing import List, Optional, Tuple

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.captions.models import CaptionSegment, CaptionStyle

logger = logging.getLogger(__name__)

# ── Default font paths ─────────────────────────────────────────
_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "fonts",
)

# Local project fonts (backend/fonts/) — keyed by weight/family name
_FONT_MAP = {
    "bold":      os.path.join(_FONTS_DIR, "Montserrat-Bold.ttf"),
    "extrabold": os.path.join(_FONTS_DIR, "Montserrat-ExtraBold.ttf"),
    "black":     os.path.join(_FONTS_DIR, "Montserrat-Black.ttf"),
    "regular":   os.path.join(_FONTS_DIR, "NunitoSans-Regular.ttf"),
    "display":   os.path.join(_FONTS_DIR, "PlayfairDisplay-Bold.ttf"),
    "mono":      os.path.join(_FONTS_DIR, "JetBrainsMono-Bold.ttf"),
}


def _find_font(font_size: int = 64, weight: str = "bold") -> Optional[ImageFont.FreeTypeFont]:
    """Find best available font for caption rendering."""
    try:
        # 1. Use project fonts first — resolve by family name
        font_path = _FONT_MAP.get(weight, _FONT_MAP.get("bold"))
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
        # 2. Fall back to any font in backend/fonts/
        if os.path.isdir(_FONTS_DIR):
            for f in os.listdir(_FONTS_DIR):
                if f.lower().endswith((".ttf", ".otf")):
                    try:
                        return ImageFont.truetype(os.path.join(_FONTS_DIR, f), font_size)
                    except Exception:
                        pass
        # 3. Windows system fonts
        win_fonts = os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), "Fonts")
        for candidate in ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"]:
            path = os.path.join(win_fonts, candidate)
            if os.path.exists(path):
                return ImageFont.truetype(path, font_size)
        return ImageFont.load_default()
    except Exception:
        return None


class BaseCaptionRenderer(ABC):
    """
    Base class for all caption renderers.
    Uses Pillow for premium-quality text rendering (RGBA transparent overlays).
    """

    def __init__(self, style: CaptionStyle, width: int = 1080, height: int = 1920):
        self.style = style
        self.width = width
        self.height = height
        # Resolve font family from style extra_params
        family = style.extra_params.get("font_family", style.font_weight)
        self._font = _find_font(style.font_size, family)
        self._family = family

    def _get_font(self, size_override: int = 0) -> ImageFont.FreeTypeFont:
        """Get font at a specific size, or default."""
        if size_override and size_override != self.style.font_size:
            return _find_font(size_override, self._family) or self._font
        return self._font

    def render_caption_frame(
        self,
        segment: CaptionSegment,
        current_time_ms: int,
    ) -> np.ndarray:
        """Render a single caption frame as a transparent BGRA NumPy array."""
        active_word_idx = self._get_active_word_idx(segment, current_time_ms)

        canvas_pil = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas_pil)

        if not segment.words:
            return self._pil_to_bgra(canvas_pil)

        text_parts = self._build_text_parts(segment, active_word_idx)
        text_y_pct = self.style.position_y_pct
        text_y = int(self.height * text_y_pct)

        self._draw_with_pillow(draw, canvas_pil, self._font, text_parts, text_y, self.style.font_size)

        return self._pil_to_bgra(canvas_pil)

    # ── Main drawing method (override in subclasses) ──────────

    def _draw_with_pillow(
        self,
        draw: ImageDraw.ImageDraw,
        canvas: Image.Image,
        font: ImageFont.FreeTypeFont,
        text_parts: List[dict],
        text_y: int,
        font_size: int,
    ):
        """Base Pillow drawing: word-by-word with active/inactive colors."""
        ep = self.style.extra_params
        uppercase = ep.get("uppercase", False)

        # Build text content
        words = []
        for p in text_parts:
            t = p["text"].upper() if uppercase else p["text"]
            words.append({**p, "text": t})

        # Measure total text width
        full_text = " ".join(w["text"] for w in words)
        bbox = draw.textbbox((0, 0), full_text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x_start = max(20, (self.width - text_w) // 2)

        # Background
        self._draw_background(draw, x_start, text_y, text_w, text_h)

        # Shadow
        shadow_offset = ep.get("shadow_offset", 2)
        shadow_alpha = ep.get("shadow_alpha", 150)
        shadow_color = self._parse_color_rgba(ep.get("shadow_color", f"rgba(0,0,0,{shadow_alpha/255:.2f})"))
        draw.text(
            (x_start + shadow_offset, text_y - text_h + shadow_offset),
            full_text, font=font, fill=shadow_color,
        )

        # Draw words individually with highlight effects
        x_pos = x_start
        for i, part in enumerate(words):
            word_text = part["text"]
            space = " " if i < len(words) - 1 else ""
            is_active = part["is_active"]

            # Get per-word color
            color = self._get_styled_color(is_active)

            # Size boost for active word
            active_boost = ep.get("active_size_boost", 0) if is_active else 0
            word_font = self._get_font(font_size + active_boost) if active_boost else font

            wb = draw.textbbox((0, 0), word_text + space, font=word_font)
            ww = wb[2] - wb[0]
            wh = wb[3] - wb[1]

            # Highlight box behind active word
            if is_active and ep.get("highlight_color"):
                pad = ep.get("highlight_padding", 6)
                hc = self._parse_color_rgba(ep["highlight_color"])
                draw.rounded_rectangle(
                    [x_pos - pad, text_y - wh - pad, x_pos + ww + pad, text_y + pad],
                    radius=6, fill=hc,
                )

            # Per-word pill bg (for active in frost_glass, bubbles, etc.)
            if is_active and ep.get("active_bg"):
                pad = ep.get("bubble_padding", 8)
                abg = self._parse_color_rgba(ep["active_bg"])
                draw.rounded_rectangle(
                    [x_pos - pad, text_y - wh - pad, x_pos + ww + pad, text_y + pad],
                    radius=12, fill=abg,
                )

            # Glow effect (draw blurred text behind active word)
            if is_active and self.style.glow:
                self._draw_glow(canvas, draw, word_text, x_pos, text_y - wh, word_font)

            # Underline on active word
            if is_active and ep.get("underline_active"):
                line_color = self._parse_color_rgba(ep.get("color_b", "#FF3CAC"))
                thickness = ep.get("underline_thickness", 3)
                wave_y = text_y + 4
                draw.line(
                    [(x_pos, wave_y), (x_pos + ww, wave_y)],
                    fill=line_color, width=thickness,
                )

            # Wave/laser underline on active word
            if is_active and (ep.get("wave_color") or ep.get("laser_color")):
                lc = self._parse_color_rgba(ep.get("wave_color", ep.get("laser_color", "#3B82F6")))
                lt = ep.get("wave_thickness", ep.get("laser_thickness", 3))
                draw.line(
                    [(x_pos, text_y + 4), (x_pos + ww, text_y + 4)],
                    fill=lc, width=lt,
                )

            # Draw the word
            draw.text((x_pos, text_y - wh), word_text + space, font=word_font, fill=color)
            x_pos += ww

        # Typewriter cursor
        if ep.get("typewriter_cursor"):
            cursor_color = self._parse_color_rgba("#FFD700")
            draw.rectangle(
                [x_pos + 2, text_y - text_h, x_pos + 6, text_y],
                fill=cursor_color,
            )

    # ── Background drawing ────────────────────────────────────

    def _draw_background(self, draw: ImageDraw.ImageDraw,
                         x_start: int, text_y: int,
                         text_w: int, text_h: int):
        """Draw background shape behind text."""
        if not self.style.bg_color or self.style.bg_color == "none":
            return

        bg = self._parse_color_rgba(self.style.bg_color)
        ep = self.style.extra_params
        shape = ep.get("bg_shape", "pill")
        pad = 24
        radius = ep.get("border_radius", 20)

        if shape == "full_bar":
            draw.rectangle(
                [0, text_y - text_h - pad, self.width, text_y + pad],
                fill=bg,
            )
        elif shape == "speech_bubble":
            draw.rounded_rectangle(
                [x_start - pad - 8, text_y - text_h - pad - 4,
                 x_start + text_w + pad + 8, text_y + pad + 4],
                radius=radius, fill=bg,
                outline=self._parse_color_rgba(self.style.outline_color) if self.style.outline_width > 0 else None,
                width=self.style.outline_width,
            )
            # Small triangle pointer
            cx = x_start + text_w // 2
            tri_y = text_y + pad + 4
            draw.polygon(
                [(cx - 10, tri_y), (cx + 10, tri_y), (cx, tri_y + 16)],
                fill=bg,
            )
        else:  # pill / default
            draw.rounded_rectangle(
                [x_start - pad, text_y - text_h - pad,
                 x_start + text_w + pad, text_y + pad],
                radius=radius, fill=bg,
            )

    # ── Glow effect ───────────────────────────────────────────

    def _draw_glow(self, canvas: Image.Image, draw: ImageDraw.ImageDraw,
                   text: str, x: int, y: int, font: ImageFont.FreeTypeFont):
        """Draw a glow behind text by rendering to a temp layer and blurring."""
        ep = self.style.extra_params
        glow_color = self._parse_color_rgba(ep.get("glow_color", "#FFFFFF"))
        radius = ep.get("glow_radius", 5)

        glow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.text((x, y), text, font=font, fill=glow_color)
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius))
        canvas.paste(Image.alpha_composite(
            Image.new("RGBA", canvas.size, (0, 0, 0, 0)),
            glow_layer,
        ), (0, 0), glow_layer)

    # ── Color helpers ─────────────────────────────────────────

    def _get_styled_color(self, is_active: bool) -> Tuple[int, int, int, int]:
        """Get color for active/inactive word from style extra_params."""
        ep = self.style.extra_params
        if is_active:
            c = ep.get("active_color", self.style.font_color)
            return self._parse_color_rgba(c)
        else:
            c = ep.get("inactive_color", None)
            if c:
                return self._parse_color_rgba(c)
            # Default: dimmed version of font_color
            base = self._parse_color_rgba(self.style.font_color)
            opacity = ep.get("inactive_opacity", 0.5)
            return (base[0], base[1], base[2], int(base[3] * opacity))

    def _get_word_color_rgba(self, is_active: bool) -> Tuple[int, int, int, int]:
        """Legacy method — routes to _get_styled_color."""
        return self._get_styled_color(is_active)

    def _parse_color_rgba(self, color_str: str) -> Tuple[int, int, int, int]:
        """Parse color string to RGBA tuple."""
        if not color_str or color_str == "none":
            return (0, 0, 0, 0)
        if color_str.startswith("rgba"):
            parts = color_str.replace("rgba(", "").replace(")", "").split(",")
            r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
            a = int(float(parts[3].strip()) * 255)
            return (r, g, b, a)
        if color_str.startswith("#"):
            h = color_str.lstrip("#")
            if len(h) == 6:
                r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return (r, g, b, 255)
            if len(h) == 8:
                r, g, b, a = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
                return (r, g, b, a)
        return (255, 255, 255, 255)

    # ── Helpers (legacy compat) ───────────────────────────────

    def _parse_color(self, color_str: str) -> Tuple[int, int, int, int]:
        """Parse color to BGRA tuple for OpenCV."""
        rgba = self._parse_color_rgba(color_str)
        return (rgba[2], rgba[1], rgba[0], rgba[3])

    def _get_word_color(self, is_active: bool) -> Tuple[int, int, int, int]:
        """BGRA color for OpenCV subclasses."""
        rgba = self._get_styled_color(is_active)
        return (rgba[2], rgba[1], rgba[0], rgba[3])

    # ── Word index + text parts ───────────────────────────────

    def _get_active_word_idx(self, segment: CaptionSegment, current_time_ms: int) -> int:
        if not self.style.word_by_word:
            return -1
        for i, word in enumerate(segment.words):
            if word.start_ms <= current_time_ms <= word.end_ms:
                return i
        return -1

    def _build_text_parts(self, segment: CaptionSegment, active_word_idx: int) -> List[dict]:
        parts = []
        for i, word in enumerate(segment.words):
            is_active = (i == active_word_idx) if self.style.word_by_word else True
            parts.append({"text": word.word, "is_active": is_active, "index": i})
        return parts

    # ── PIL ↔ OpenCV converters ───────────────────────────────

    def _pil_to_bgra(self, pil_image: Image.Image) -> np.ndarray:
        """Convert PIL RGBA image to NumPy BGRA array."""
        rgba = np.array(pil_image, dtype=np.uint8)
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        return bgra

    def _bgra_canvas_to_pil(self, canvas: np.ndarray) -> Image.Image:
        """Convert BGRA NumPy array to PIL RGBA image."""
        rgba = cv2.cvtColor(canvas, cv2.COLOR_BGRA2RGBA)
        return Image.fromarray(rgba, "RGBA")

    # ── Legacy OpenCV fallback ────────────────────────────────

    def _draw_text_on_canvas(self, canvas, text_parts, text_y):
        """OpenCV fallback for subclasses that override this."""
        font = cv2.FONT_HERSHEY_DUPLEX
        scale = self.style.font_size / 36.0
        thickness = max(2, int(scale * 1.5))
        full_text = " ".join(p["text"] for p in text_parts)
        (total_w, text_h), _ = cv2.getTextSize(full_text, font, scale, thickness)
        x_start = max(20, (self.width - total_w) // 2)
        if self.style.bg_color and self.style.bg_color != "none":
            bg_color = self._parse_color(self.style.bg_color)
            pad = 20
            cv2.rectangle(canvas,
                          (x_start - pad, text_y - text_h - pad),
                          (x_start + total_w + pad, text_y + pad),
                          bg_color, -1)
        x_pos = x_start
        for part in text_parts:
            word_text = part["text"] + " "
            (word_w, _), _ = cv2.getTextSize(word_text, font, scale, thickness)
            color = self._get_word_color(part["is_active"])
            if self.style.outline_width > 0:
                outline = self._parse_color(self.style.outline_color)
                cv2.putText(canvas, word_text, (x_pos, text_y), font, scale,
                            (*outline[:3], 255), thickness + self.style.outline_width)
            cv2.putText(canvas, word_text, (x_pos, text_y), font, scale,
                        (*color[:3], 255), thickness)
            x_pos += word_w


# Backward-compatible alias (old renderers import this name)
ImageMagickCaptionRenderer = BaseCaptionRenderer
