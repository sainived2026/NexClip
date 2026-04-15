"""14 — Documentary Tag Renderer
Bottom-left, left-aligned italic Playfair with TRANSCRIPT label + white rule line.
Inactive: rgba(255,255,255,0.4). Active: #F5E6C8.
"""
from PIL import ImageDraw, ImageFont, Image
from typing import List
from app.captions.renderers.base_renderer import BaseCaptionRenderer, _find_font


class DocumentaryTagRenderer(BaseCaptionRenderer):
    def _draw_with_pillow(self, draw: ImageDraw.ImageDraw, canvas: Image.Image,
                          font: ImageFont.FreeTypeFont, text_parts: List[dict],
                          text_y: int, font_size: int):
        words = [{**p, "text": p["text"]} for p in text_parts]
        bbox = draw.textbbox((0, 0), "A", font=font)
        text_h = bbox[3] - bbox[1]

        # Left-aligned at bottom left
        x_start = int(self.width * 0.06)  # ~6% from left edge

        # ── TRANSCRIPT label (small caps) ──
        label_font = _find_font(int(font_size * 0.35), "extrabold") or font
        label_text = "TRANSCRIPT"
        lbbox = draw.textbbox((0, 0), label_text, font=label_font)
        label_h = lbbox[3] - lbbox[1]

        # Position label above the captions
        label_y = text_y - text_h - label_h - 16
        draw.text((x_start, label_y), label_text, font=label_font,
                  fill=(255, 255, 255, 180))

        # ── 28px white rule line ──
        line_y = text_y - text_h - 8
        draw.line(
            [(x_start, line_y), (x_start + 28, line_y)],
            fill=(255, 255, 255, 255), width=2,
        )

        # ── Caption words (left-aligned) ──
        x_pos = x_start
        for i, part in enumerate(words):
            word_text = part["text"] + (" " if i < len(words) - 1 else "")
            is_active = part["is_active"]
            wb = draw.textbbox((0, 0), word_text, font=font)
            ww = wb[2] - wb[0]

            if is_active:
                color = (245, 230, 200, 255)  # warm cream #F5E6C8
            else:
                color = (255, 255, 255, 102)  # 0.4 * 255 ≈ 102

            draw.text((x_pos, text_y - text_h), word_text, font=font, fill=color)
            x_pos += ww
