"""08 — LinkedIn Clean Renderer
Minimal professional, subtle ghost to white. No decoration.
Inactive: rgba(255,255,255,0.28). Active: #FFFFFF.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class LinkedInCleanRenderer(BaseCaptionRenderer):
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
            wb = draw.textbbox((0, 0), word_text, font=font)
            ww = wb[2] - wb[0]

            if is_active:
                color = (255, 255, 255, 255)
            else:
                color = (255, 255, 255, 71)  # 0.28 * 255 ≈ 71

            draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)
            x_pos += ww
