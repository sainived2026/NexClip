"""03 — Cinematic Lower Renderer
Bottom-positioned italic Playfair, warm cream active — NO background bar.
Inactive: rgba(220,220,220,0.45). Active: #F5E6C8.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class CinematicLowerRenderer(BaseCaptionRenderer):
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
                color = (245, 230, 200, 255)  # warm cream #F5E6C8
            else:
                color = (220, 220, 220, 115)  # rgba(220,220,220,0.45)

            draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)
            x_pos += ww
