"""06 — Serif Story Renderer
Italic Playfair, warm cream active with scale 1.04.
Inactive: rgba(255,255,255,0.4). Active: #F5E6C8.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class SerifStoryRenderer(BaseCaptionRenderer):
    def _draw_with_pillow(self, draw: ImageDraw.ImageDraw, canvas: Image.Image,
                          font: ImageFont.FreeTypeFont, text_parts: List[dict],
                          text_y: int, font_size: int):
        words = [{**p, "text": p["text"]} for p in text_parts]
        full_text = " ".join(w["text"] for w in words)
        bbox = draw.textbbox((0, 0), full_text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x_start = max(20, (self.width - text_w) // 2)

        x_pos = x_start
        for i, part in enumerate(words):
            word_text = part["text"] + (" " if i < len(words) - 1 else "")
            is_active = part["is_active"]

            if is_active:
                active_font = self._get_font(int(font_size * 1.04))
                color = (245, 230, 200, 255)  # #F5E6C8
                wb = draw.textbbox((0, 0), word_text, font=active_font)
                ww = wb[2] - wb[0]
                active_h = wb[3] - wb[1]
                draw.text((x_pos, text_y - active_h), word_text, font=active_font, fill=color)
            else:
                color = (255, 255, 255, 102)  # 0.4 * 255 ≈ 102
                wb = draw.textbbox((0, 0), word_text, font=font)
                ww = wb[2] - wb[0]
                draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)

            x_pos += ww
