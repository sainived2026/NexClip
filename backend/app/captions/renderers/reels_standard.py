"""09 — Reels Standard Renderer
White stroked, cyan active. Both have 3px black stroke.
Inactive: #FFFFFF + stroke. Active: #00C2FF + same stroke.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class ReelsStandardRenderer(BaseCaptionRenderer):
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
                color = (0, 194, 255, 255)  # #00C2FF cyan
            else:
                color = (255, 255, 255, 255)

            draw.text((x_pos, text_y - text_h), word_text, font=font,
                      fill=color, stroke_width=3, stroke_fill=(0, 0, 0, 255))
            x_pos += ww
