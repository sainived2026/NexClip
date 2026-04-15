"""10 — Prestige Serif Renderer
Italic Playfair with letter-spacing 1.5px, ghost to white with scale 1.06.
Inactive: rgba(255,255,255,0.35). Active: #FFFFFF + scale.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class PrestigeSerifRenderer(BaseCaptionRenderer):
    LETTER_SPACING = 2  # approximate 1.5px at rendering scale

    def _draw_spaced_text(self, draw, x, y, text, font, fill):
        for ch in text:
            draw.text((x, y), ch, font=font, fill=fill)
            cb = draw.textbbox((0, 0), ch, font=font)
            x += (cb[2] - cb[0]) + self.LETTER_SPACING
        return x

    def _measure_spaced(self, draw, text, font):
        w = 0
        for ch in text:
            cb = draw.textbbox((0, 0), ch, font=font)
            w += (cb[2] - cb[0]) + self.LETTER_SPACING
        return max(0, w - self.LETTER_SPACING) if text else 0

    def _draw_with_pillow(self, draw: ImageDraw.ImageDraw, canvas: Image.Image,
                          font: ImageFont.FreeTypeFont, text_parts: List[dict],
                          text_y: int, font_size: int):
        words = [{**p, "text": p["text"]} for p in text_parts]

        total_w = 0
        for i, w in enumerate(words):
            total_w += self._measure_spaced(draw, w["text"], font)
            if i < len(words) - 1:
                total_w += self._measure_spaced(draw, " ", font) + self.LETTER_SPACING

        x_start = max(20, (self.width - total_w) // 2)
        bbox = draw.textbbox((0, 0), "A", font=font)
        text_h = bbox[3] - bbox[1]

        x_pos = x_start
        for i, part in enumerate(words):
            is_active = part["is_active"]
            word_text = part["text"]

            if is_active:
                active_font = self._get_font(int(font_size * 1.06))
                color = (255, 255, 255, 255)
                ab = draw.textbbox((0, 0), "A", font=active_font)
                ah = ab[3] - ab[1]
                x_pos = self._draw_spaced_text(draw, x_pos, text_y - ah, word_text, active_font, color)
            else:
                color = (255, 255, 255, 89)  # 0.35 * 255 ≈ 89
                x_pos = self._draw_spaced_text(draw, x_pos, text_y - text_h, word_text, font, color)

            if i < len(words) - 1:
                x_pos += self._measure_spaced(draw, " ", font) + self.LETTER_SPACING
