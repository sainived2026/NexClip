"""18 — Warm Serif Glow Renderer
Italic Playfair, warm cream glow, letter-spacing 1px, scale 1.08.
Inactive: rgba(255,255,255,0.32). Active: #F5E0B0 with scale.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class WarmSerifGlowRenderer(BaseCaptionRenderer):
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
                # Scale 1.08 — use larger font
                active_font = self._get_font(int(font_size * 1.08))
                color = (245, 224, 176, 255)  # warm cream #F5E0B0
                wb = draw.textbbox((0, 0), word_text, font=active_font)
                ww = wb[2] - wb[0]
                active_h = wb[3] - wb[1]
                draw.text((x_pos, text_y - active_h), word_text, font=active_font, fill=color)
            else:
                color = (255, 255, 255, 82)  # 0.32 * 255 ≈ 82
                wb = draw.textbbox((0, 0), word_text, font=font)
                ww = wb[2] - wb[0]
                draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)

            x_pos += ww
