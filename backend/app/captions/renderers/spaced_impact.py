"""12 — Spaced Impact Renderer
Ultra-wide letter-spacing 8px, UPPERCASE, ghost to white.
Inactive: rgba(255,255,255,0.22). Active: #FFFFFF.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class SpacedImpactRenderer(BaseCaptionRenderer):
    LETTER_SPACING = 8

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
        words = [{**p, "text": p["text"].upper()} for p in text_parts]

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

            if is_active:
                color = (255, 255, 255, 255)
            else:
                color = (255, 255, 255, 56)  # 0.22 * 255

            x_pos = self._draw_spaced_text(draw, x_pos, text_y - text_h, part["text"], font, color)
            if i < len(words) - 1:
                x_pos += self._measure_spaced(draw, " ", font) + self.LETTER_SPACING
