"""15 — Feather Light Renderer
NunitoSans-Regular, weight shift only on active (renders bold font).
Inactive: rgba(255,255,255,0.32). Active: #FFFFFF with bold weight.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer, _find_font


class FeatherLightRenderer(BaseCaptionRenderer):
    LETTER_SPACING = 1

    def _draw_with_pillow(self, draw: ImageDraw.ImageDraw, canvas: Image.Image,
                          font: ImageFont.FreeTypeFont, text_parts: List[dict],
                          text_y: int, font_size: int):
        words = [{**p, "text": p["text"]} for p in text_parts]
        # Bold font for active word (weight shift = font-weight 800)
        bold_font = _find_font(font_size, "extrabold") or font

        full_text = " ".join(w["text"] for w in words)
        bbox = draw.textbbox((0, 0), full_text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x_start = max(20, (self.width - text_w) // 2)

        x_pos = x_start
        for i, part in enumerate(words):
            word_text = part["text"] + (" " if i < len(words) - 1 else "")
            is_active = part["is_active"]

            if is_active:
                # Weight shift only — use bold font, full opacity
                color = (255, 255, 255, 255)
                wb = draw.textbbox((0, 0), word_text, font=bold_font)
                ww = wb[2] - wb[0]
                wh = wb[3] - wb[1]
                draw.text((x_pos, text_y - wh), word_text, font=bold_font, fill=color)
            else:
                color = (255, 255, 255, 82)  # 0.32 * 255 ≈ 82
                wb = draw.textbbox((0, 0), word_text, font=font)
                ww = wb[2] - wb[0]
                draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)

            x_pos += ww
