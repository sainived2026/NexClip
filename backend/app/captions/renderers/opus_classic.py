"""01 — Opus Classic Renderer
White stroked text, yellow highlight box on active word, black text on yellow.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class OpusClassicRenderer(BaseCaptionRenderer):
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
            ww, wh = wb[2] - wb[0], bbox[3] - bbox[1]

            if is_active:
                # Yellow highlight box behind active word
                pad = 6
                draw.rounded_rectangle(
                    [x_pos - pad, text_y - wh - pad, x_pos + ww + pad, text_y + pad],
                    radius=4, fill=(255, 230, 0, 255),
                )
                # Black text, no stroke
                draw.text((x_pos, text_y - wh), word_text, font=font, fill=(0, 0, 0, 255))
            else:
                # White text with 3px black stroke
                draw.text((x_pos, text_y - wh), word_text, font=font,
                          fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

            x_pos += ww
