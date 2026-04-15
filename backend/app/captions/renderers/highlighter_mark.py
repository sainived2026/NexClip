"""11 — Highlighter Mark Renderer
Ghost text, yellow highlight rectangle behind active word.
Inactive: rgba(255,255,255,0.32). Active: #FFFFFF + rgba(255,214,0,0.22) filled rect.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class HighlighterMarkRenderer(BaseCaptionRenderer):
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

            if is_active:
                # Yellow highlight rectangle: rgba(255,214,0,0.22) + 6px padding, rx=4
                pad = 6
                draw.rounded_rectangle(
                    [x_pos - pad, text_y - text_h - pad, x_pos + ww_only + pad, text_y + pad],
                    radius=4, fill=(255, 214, 0, 56),  # 0.22 * 255 ≈ 56
                )
                color = (255, 255, 255, 255)
            else:
                color = (255, 255, 255, 82)  # 0.32 * 255 ≈ 82

            draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)
            x_pos += ww
