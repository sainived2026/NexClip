"""13 — Ghost Pill Renderer
Ghost words with invisible border placeholder. Active: white + capsule border appears.
Inactive: rgba(255,255,255,0.35). Active: #FFFFFF + 2px border capsule.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class GhostPillRenderer(BaseCaptionRenderer):
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
            word_only = part["text"]
            is_active = part["is_active"]
            wb = draw.textbbox((0, 0), word_text, font=font)
            ww = wb[2] - wb[0]
            wb_only = draw.textbbox((0, 0), word_only, font=font)
            ww_only = wb_only[2] - wb_only[0]

            pad_x, pad_y = 18, 6

            if is_active:
                # Capsule border: 2px solid rgba(255,255,255,0.85), rx=30
                draw.rounded_rectangle(
                    [x_pos - pad_x, text_y - text_h - pad_y,
                     x_pos + ww_only + pad_x, text_y + pad_y],
                    radius=30,
                    fill=None,
                    outline=(255, 255, 255, 217),  # 0.85 * 255 ≈ 217
                    width=2,
                )
                color = (255, 255, 255, 255)
            else:
                color = (255, 255, 255, 89)  # 0.35 * 255 ≈ 89

            draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)
            x_pos += ww
