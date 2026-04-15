"""
NexRenderer Engine — Pillow Renderer Module (v2)
Draws CSS-like typography, containers, and effects using Python PIL.
FIXED: Font path resolution, word positioning, container rendering.
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from app.captions.models import CaptionStyle, CaptionSegment
from app.captions.engine.animator import parse_color, Animator

# ── Font Loading ──────────────────────────────────────────────────
_FONT_CACHE = {}

# Resolve font directory ONCE at module load (backend/fonts)
_FONT_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),  # app/captions/engine
    "..", "..", "..", "fonts"                     # -> backend/fonts
))


def get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TrueType font from backend/fonts with cache."""
    size = max(10, int(size))
    key = f"{font_name}_{size}"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    font_path = os.path.join(_FONT_DIR, font_name)
    if not os.path.isfile(font_path):
        # Try fallback
        font_path = os.path.join(_FONT_DIR, "Montserrat-ExtraBold.ttf")

    try:
        font = ImageFont.truetype(font_path, size)
    except Exception:
        # Last resort — should never happen if fonts dir is correct
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


# ── Helpers ───────────────────────────────────────────────────────

def _rgba(c) -> tuple:
    """Convenience wrapper: parse_color but always returns 4-tuple."""
    if isinstance(c, tuple):
        return c
    if c is None or c == "none":
        return (0, 0, 0, 0)
    return parse_color(c)


def _draw_rounded_rect(draw, xy, radius, fill, outline=None, width=0):
    """Draw a rounded rectangle. xy = [(x0,y0),(x1,y1)]."""
    r = max(0, int(radius))
    draw.rounded_rectangle(xy, radius=r, fill=fill,
                           outline=outline if width > 0 else None,
                           width=max(1, int(width)) if width > 0 else 0)


def _gradient_image(w, h, colors, angle_deg=135):
    """Create a PIL RGBA gradient image from a list of hex colors."""
    if not colors or len(colors) < 2:
        c = _rgba(colors[0]) if colors else (100, 100, 100, 255)
        return Image.new("RGBA", (int(w), int(h)), c)

    arr = np.zeros((int(h), int(w), 4), dtype=np.uint8)
    rgba_colors = [_rgba(c) for c in colors]
    n = len(rgba_colors)

    # Create gradient along the angle
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    for y in range(int(h)):
        for x in range(int(w)):
            # Project point onto gradient axis
            t = (x * cos_a + y * sin_a) / (w * abs(cos_a) + h * abs(sin_a))
            t = max(0.0, min(1.0, t))

            # Find which color segment we're in
            seg = t * (n - 1)
            idx = min(int(seg), n - 2)
            frac = seg - idx

            c1, c2 = rgba_colors[idx], rgba_colors[idx + 1]
            arr[y, x] = [
                int(c1[0] + (c2[0] - c1[0]) * frac),
                int(c1[1] + (c2[1] - c1[1]) * frac),
                int(c1[2] + (c2[2] - c1[2]) * frac),
                int(c1[3] + (c2[3] - c1[3]) * frac),
            ]
    return Image.fromarray(arr, "RGBA")


def _gradient_text(text, font, colors):
    """Render text filled with a horizontal gradient. Returns RGBA Image."""
    # Measure text
    tmp = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(tmp)
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0] + 4
    th = bbox[3] - bbox[1] + 4

    # Create gradient
    grad = _gradient_image(tw, th, colors, angle_deg=0)

    # Create text mask (white text on black)
    mask_img = Image.new("L", (tw, th), 0)
    md = ImageDraw.Draw(mask_img)
    md.text((-bbox[0] + 2, -bbox[1] + 2), text, font=font, fill=255)

    # Apply mask to gradient
    result = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    result.paste(grad, mask=mask_img)
    return result


# ── Main Renderer ─────────────────────────────────────────────────

class PillowRenderer:
    def __init__(self, style: CaptionStyle, width: int, height: int):
        self.style = style
        self.width = width
        self.height = height

        # Responsive scaling: 16:9 captions must be BIGGER than 9:16
        if width > height:
            # Landscape 16:9 — scale up extra
            self.scale = (width / 1080.0) * 1.15
        else:
            # Portrait 9:16
            self.scale = width / 1080.0

        self.base_font_size = max(16, int(self.style.font_size * self.scale))
        self.font = get_font(self.style.font_family, self.base_font_size)
        self._s = self.scale  # shorthand

    # ── Shadow Drawing ────────────────────────────────────────────
    def _draw_shadows(self, canvas, text, font, cx, cy, shadows, scale=1.0):
        if not shadows:
            return
        for s in shadows:
            dx = int(s.get("dx", 0) * self._s * scale)
            dy = int(s.get("dy", 0) * self._s * scale)
            blur = int(s.get("blur", 0) * self._s)
            color = _rgba(s.get("color", "#000000"))

            if blur > 0:
                layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                ld.text((cx + dx, cy + dy), text, font=font, fill=color, anchor="mm")
                layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))
                canvas.alpha_composite(layer)
            else:
                draw = ImageDraw.Draw(canvas)
                draw.text((cx + dx, cy + dy), text, font=font, fill=color, anchor="mm")

    # ── Measure word widths ───────────────────────────────────────
    def _measure_words(self, words_str, font, spacing):
        """Return list of (word_str, word_pixel_width) for layout."""
        tmp = Image.new("RGBA", (1, 1))
        d = ImageDraw.Draw(tmp)
        result = []
        for w in words_str:
            tw = d.textlength(w, font=font) + spacing
            result.append((w, tw))
        return result

    # ── Main Frame Render ─────────────────────────────────────────
    def render_frame(self, segment: CaptionSegment, current_ms: int) -> Image.Image:
        canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        s = self._s
        style = self.style

        # Prepare word strings
        words_str = []
        for w in segment.words:
            ws = w.word.upper() if style.uppercase else w.word
            words_str.append(ws)

        spacing = int(style.letter_spacing * s)

        # Measure each word
        word_metrics = self._measure_words(words_str, self.font, spacing)
        gap = int(8 * s)  # gap between words

        # Calculate total line width
        total_text_w = sum(wm[1] for wm in word_metrics) + gap * max(0, len(word_metrics) - 1)

        # Add prefix width if any
        prefix_w = 0
        if style.prefix:
            prefix_w = draw.textlength(style.prefix, font=self.font) + gap

        total_line_w = prefix_w + total_text_w

        # Determine Y position based on style.position
        pos = style.position
        if pos in ("bottom-center", "bottom-bar"):
            center_y = int(self.height * 0.88)
        elif pos == "center-bottom":
            center_y = int(self.height * 0.78)
        else:
            center_y = int(self.height * 0.72)

        # Measure text height
        bbox = draw.textbbox((0, 0), "Ay", font=self.font)
        text_h = bbox[3] - bbox[1]

        pad_v = int(style.padding[0] * s)
        pad_h = int(style.padding[1] * s)

        # ── Draw full-width BAR containers ────────────────────────
        if style.container_type == "bar":
            bar_color = _rgba(style.bg_color)
            bar_y1 = center_y - text_h // 2 - pad_v
            bar_y2 = center_y + text_h // 2 + pad_v

            if style.border_radius > 0:
                _draw_rounded_rect(draw,
                                   [(pad_h, bar_y1), (self.width - pad_h, bar_y2)],
                                   int(style.border_radius * s), fill=bar_color,
                                   outline=_rgba(style.border_color), width=int(style.border_width * s))
            else:
                draw.rectangle([(0, bar_y1), (self.width, bar_y2)], fill=bar_color)

        # ── Draw single PILL container around the whole line ──────
        elif style.container_type == "pill":
            pill_x1 = (self.width - total_line_w) // 2 - pad_h
            pill_x2 = (self.width + total_line_w) // 2 + pad_h
            pill_y1 = center_y - text_h // 2 - pad_v
            pill_y2 = center_y + text_h // 2 + pad_v

            bg = style.bg_color
            if isinstance(bg, str) and bg.startswith("gradient:"):
                # Parse "gradient:135deg:#667EEA,#764BA2"
                parts = bg.split(":")
                angle = int(parts[1].replace("deg", ""))
                colors = parts[2].split(",")
                grad = _gradient_image(pill_x2 - pill_x1, pill_y2 - pill_y1, colors, angle)
                # Paste gradient with rounded mask
                mask = Image.new("L", grad.size, 0)
                md = ImageDraw.Draw(mask)
                md.rounded_rectangle([(0, 0), (grad.size[0] - 1, grad.size[1] - 1)],
                                     radius=int(style.border_radius * s), fill=255)
                canvas.paste(grad, (int(pill_x1), int(pill_y1)), mask)
            else:
                _draw_rounded_rect(draw,
                                   [(pill_x1, pill_y1), (pill_x2, pill_y2)],
                                   int(style.border_radius * s), fill=_rgba(bg))

        # ── Retrowave top-border line ─────────────────────────────
        if style.style_id == "retrowave":
            line_y = center_y - text_h // 2 - pad_v - int(6 * s)
            line_x1 = (self.width - total_line_w) // 2 - int(20 * s)
            line_x2 = (self.width + total_line_w) // 2 + int(20 * s)
            draw.rectangle([(line_x1, line_y), (line_x2, line_y + int(3 * s))],
                           fill=_rgba("#7B00FF"))

        # ── Breaking Alert "LIVE" badge ───────────────────────────
        if style.style_id == "breaking_alert":
            badge_font_size = int(22 * s)
            badge_font = get_font("Montserrat-Black.ttf", badge_font_size)
            badge_text = "LIVE"
            badge_tw = draw.textlength(badge_text, font=badge_font)
            badge_h = int(badge_font_size * 1.4)
            badge_pad = int(10 * s)
            badge_x = int(20 * s)
            badge_cy = center_y

            # White pill with red text
            _draw_rounded_rect(draw,
                               [(badge_x, badge_cy - badge_h // 2),
                                (badge_x + badge_tw + badge_pad * 2, badge_cy + badge_h // 2)],
                               radius=int(4 * s), fill=(255, 255, 255, 255))
            draw.text((badge_x + badge_pad + badge_tw // 2, badge_cy),
                      badge_text, font=badge_font, fill=_rgba("#CC0000"), anchor="mm")

            # Shift word start after badge
            prefix_w = badge_x + badge_tw + badge_pad * 2 + int(16 * s)
            total_line_w = prefix_w + total_text_w

        # ── Starting X for word rendering ─────────────────────────
        if style.style_id == "breaking_alert":
            cursor_x = prefix_w
        else:
            cursor_x = (self.width - total_line_w) / 2.0
            # Add prefix
            if style.prefix:
                p_color = _rgba(style.prefix_color)
                draw.text((int(cursor_x + prefix_w / 2), center_y),
                          style.prefix, font=self.font, fill=p_color, anchor="mm")
                cursor_x += prefix_w

        # ── Render each word ──────────────────────────────────────
        for i, word_obj in enumerate(segment.words):
            word_str = words_str[i]
            base_w = word_metrics[i][1]

            is_active = word_obj.start_ms <= current_ms <= word_obj.end_ms

            # Animation state
            target_scale = style.active_scale if is_active else 1.0
            anim = Animator.get_state(
                current_ms, word_obj.start_ms, word_obj.end_ms,
                style.animation_type, 1.0, target_scale
            )
            anim_scale = anim["scale"]

            # Font for this word
            w_font = self.font
            if anim_scale != 1.0 and is_active:
                w_font = get_font(style.font_family, int(self.base_font_size * anim_scale))

            # Colors
            w_color = _rgba(style.active_color) if is_active and style.active_color else _rgba(style.color)
            w_bg = _rgba(style.active_bg_color) if is_active and style.active_bg_color else None
            w_shadows = style.active_text_shadow if is_active and style.active_text_shadow is not None else style.text_shadow

            # Center of this word
            wcx = cursor_x + base_w / 2
            wcy = center_y

            # ── Draw WORD-PILL backgrounds ────────────────────────
            if style.container_type == "word-pill":
                # Decide background color
                if is_active and style.active_bg_color:
                    pill_bg = _rgba(style.active_bg_color)
                elif style.bg_color and style.bg_color != "rgba(0,0,0,0)":
                    pill_bg = _rgba(style.bg_color)
                else:
                    pill_bg = None

                # Special: sticker_swap cycles colors per word position
                if style.style_id == "sticker_swap" and is_active and style.gradient_colors:
                    ci = i % len(style.gradient_colors)
                    pill_bg = _rgba(style.gradient_colors[ci])

                if pill_bg and pill_bg[3] > 0:
                    pw = base_w + pad_h * 2
                    ph = text_h + pad_v * 2
                    px1 = wcx - pw / 2
                    py1 = wcy - ph / 2
                    px2 = wcx + pw / 2
                    py2 = wcy + ph / 2

                    # Border
                    b_color = _rgba(style.active_border_color) if is_active and style.active_border_color else _rgba(style.border_color)
                    b_width = (style.active_border_width or 0) if is_active and style.active_border_width else style.border_width
                    rad = style.border_radius

                    _draw_rounded_rect(draw,
                                       [(int(px1), int(py1)), (int(px2), int(py2))],
                                       int(rad * s), fill=pill_bg,
                                       outline=b_color if b_width > 0 else None,
                                       width=int(b_width * s))

            # ── Active word highlight BG (non-pill styles) ────────
            elif w_bg and w_bg[3] > 0 and style.container_type != "bar":
                tw = draw.textlength(word_str, font=w_font) + int(8 * s)
                bx1 = wcx - tw / 2 - int(4 * s)
                by1 = wcy - text_h / 2 - int(2 * s)
                bx2 = wcx + tw / 2 + int(4 * s)
                by2 = wcy + text_h / 2 + int(2 * s)
                _draw_rounded_rect(draw,
                                   [(int(bx1), int(by1)), (int(bx2), int(by2))],
                                   int(4 * s), fill=w_bg)

            # ── Retrowave active word bg ──────────────────────────
            if style.style_id == "retrowave" and is_active:
                abg = _rgba("#4A0070")
                tw = draw.textlength(word_str, font=w_font) + int(16 * s)
                bx1 = wcx - tw / 2
                by1 = wcy - text_h / 2 - int(2 * s)
                bx2 = wcx + tw / 2
                by2 = wcy + text_h / 2 + int(2 * s)
                _draw_rounded_rect(draw,
                                   [(int(bx1), int(by1)), (int(bx2), int(by2))],
                                   int(4 * s), fill=abg)

            # ── Underline for active word (underline_score) ───────
            if style.style_id == "underline_score" and is_active:
                tw = draw.textlength(word_str, font=w_font)
                ux1 = wcx - tw / 2
                ux2 = wcx + tw / 2
                uy = wcy + text_h / 2 + int(4 * s)
                draw.rectangle([(int(ux1), int(uy)), (int(ux2), int(uy + 4 * s))],
                               fill=_rgba("#00D4FF"))

            # ── Draw Shadows ──────────────────────────────────────
            self._draw_shadows(canvas, word_str, w_font, int(wcx), int(wcy), w_shadows)

            # ── Draw the text ─────────────────────────────────────
            # Special: holographic active word gets gradient text
            if style.style_id == "holographic" and is_active and style.gradient_colors:
                grad_img = _gradient_text(word_str, w_font, style.gradient_colors)
                gw, gh = grad_img.size
                paste_x = int(wcx - gw / 2)
                paste_y = int(wcy - gh / 2)
                canvas.alpha_composite(grad_img, (paste_x, paste_y))
            else:
                draw = ImageDraw.Draw(canvas)  # re-acquire after alpha_composite
                draw.text((int(wcx), int(wcy)), word_str, font=w_font, fill=w_color, anchor="mm")

            # Advance cursor
            cursor_x += base_w + gap

        return canvas
