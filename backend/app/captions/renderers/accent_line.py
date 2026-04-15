"""17 — Accent Line Renderer
Ghost words, white active with 3.5px border-bottom drawn 4px below baseline.
Inactive: rgba(255,255,255,0.35). Active: #FFFFFF + bottom underline.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer


class AccentLineRenderer(BaseCaptionRenderer):
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
                color = (255, 255, 255, 255)
                draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)
                # Accent line: 3.5px (round to 4) solid white, 4px below baseline
                line_y = text_y + 4
                draw.line([(x_pos, line_y), (x_pos + ww_only, line_y)],
                          fill=(255, 255, 255, 255), width=4)
            else:
                # Ghost with transparent 3px bottom placeholder (invisible line)
                color = (255, 255, 255, 89)  # 0.35 * 255 ≈ 89
                draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)

            x_pos += ww
