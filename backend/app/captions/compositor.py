"""
NexClip — Caption Compositor (ASS Engine v4)
Generates Advanced SubStation Alpha subtitles with word-by-word highlighting.
Burns captions into video using FFmpeg libass for cinema-quality text rendering.

18 Premium Caption Styles — matching the Pillow renderers:
  01 Opus Classic       02 Ghost Karaoke       03 Cinematic Lower
  04 All-Caps Tracker   05 Underline Reveal    06 Serif Story
  07 MrBeast Bold       08 LinkedIn Clean      09 Reels Standard
  10 Prestige Serif     11 Highlighter Mark    12 Spaced Impact
  13 Ghost Pill         14 Documentary Tag     15 Feather Light
  16 Stroked Uppercase  17 Accent Line         18 Warm Serif Glow
"""
import os, time, logging, tempfile, subprocess
from typing import List
from app.captions.models import CaptionStyle, CaptionSegment
from app.core.binaries import get_ffmpeg_path

logger = logging.getLogger(__name__)

FONTS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fonts"))


def _c(hex_color):
    """#RRGGBB → ASS inline &HBBGGRR&"""
    h = hex_color.lstrip("#")
    return f"&H{int(h[4:6], 16):02X}{int(h[2:4], 16):02X}{int(h[0:2], 16):02X}&"


def _cs(hex_color, alpha=0):
    """#RRGGBB → ASS style &HAABBGGRR"""
    h = hex_color.lstrip("#")
    return f"&H{alpha:02X}{int(h[4:6], 16):02X}{int(h[2:4], 16):02X}{int(h[0:2], 16):02X}"


def _t(ms):
    """ms → ASS time H:MM:SS.CC"""
    ms = max(0, ms)
    cs = (ms // 10) % 100
    s, m = (ms // 1000) % 60, (ms // 60000) % 60
    return f"{ms // 3600000}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(t):
    return t.replace("\\", "/").replace("{", "").replace("}", "")


def _get_config(style_id, w, h):
    """Return complete ASS config for each of the 18 styles."""
    sc = (w / 1080.0) * 1.15 if w > h else w / 1080.0
    cx, cy = w // 2, int(h * 0.72)
    by = h - int(60 * sc)
    bl_x = int(80 * sc)
    brd = lambda v: int(v * sc)

    C = {
        # ── 01 Opus Classic ──
        # Inactive: white + 3px black stroke. Active: yellow bg, black text, no stroke.
        "opus_classic": dict(
            font="Montserrat-ExtraBold", sz=brd(58), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=brd(3), shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="", iex="",
            a1c=_c("#000000"), a3c=_c("#FFE600"), a3a="\\3a&H00&", aex="\\bord0\\bs3\\3c" + _c("#FFE600"),
        ),
        # ── 02 Ghost Karaoke ──
        # Inactive: white 35% opacity. Active: white 100% + scale 1.05.
        "ghost_karaoke": dict(
            font="Montserrat-Bold", sz=brd(54), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H96&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\fscx105\\fscy105",
        ),
        # ── 03 Cinematic Lower ──
        # Bottom position, italic Playfair. Inactive: 45% opacity. Active: warm cream.
        "cinematic_lower": dict(
            font="PlayfairDisplay-Bold", sz=brd(48), bold=-1, italic=1, upper=False,
            an=2, px=cx, py=by, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#DCDCDC"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H6E&",
            a1c=_c("#F5E6C8"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&",
        ),
        # ── 04 All-Caps Tracker ──
        # UPPERCASE, 5px spacing. Inactive: 22% opacity. Active: white.
        "allcaps_tracker": dict(
            font="Montserrat-Black", sz=brd(52), bold=-1, italic=0, upper=True,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=brd(5),
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&HC8&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&",
        ),
        # ── 05 Underline Reveal ──
        # Inactive: 45% opacity. Active: white + underline.
        "underline_reveal": dict(
            font="Montserrat-Bold", sz=brd(52), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H6E&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\u1",
        ),
        # ── 06 Serif Story ──
        # Italic Playfair. Inactive: 40% opacity. Active: warm cream + scale 1.04.
        "serif_story": dict(
            font="PlayfairDisplay-Bold", sz=brd(50), bold=-1, italic=1, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H66&",
            a1c=_c("#F5E6C8"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\fscx104\\fscy104",
        ),
        # ── 07 MrBeast Bold ──
        # UPPERCASE. Inactive: white + 3.5px stroke. Active: orange + stroke + scale 1.06.
        "mrbeast_bold": dict(
            font="Montserrat-Black", sz=brd(62), bold=-1, italic=0, upper=True,
            an=5, px=cx, py=cy, bs=1, ol=brd(4), shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="", iex="",
            a1c=_c("#FF6B00"), a3c=_c("#000000"), a3a="", aex="\\fscx106\\fscy106",
        ),
        # ── 08 LinkedIn Clean ──
        # Inactive: 28% opacity. Active: white.
        "linkedin_clean": dict(
            font="Montserrat-Bold", sz=brd(50), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&HB8&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&",
        ),
        # ── 09 Reels Standard ──
        # Inactive: white + 3px stroke. Active: cyan + same stroke.
        "reels_standard": dict(
            font="Montserrat-ExtraBold", sz=brd(56), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=brd(3), shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="", iex="",
            a1c=_c("#00C2FF"), a3c=_c("#000000"), a3a="", aex="",
        ),
        # ── 10 Prestige Serif ──
        # Italic, 1.5px spacing. Inactive: 35% opacity. Active: white + scale 1.06.
        "prestige_serif": dict(
            font="PlayfairDisplay-Bold", sz=brd(52), bold=-1, italic=1, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=brd(2),
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H96&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\fscx106\\fscy106",
        ),
        # ── 11 Highlighter Mark ──
        # Inactive: 32% opacity. Active: white + yellow filled rect behind word.
        "highlighter_mark": dict(
            font="Montserrat-ExtraBold", sz=brd(56), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=3, ol=brd(6), shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&HAE&",
            a1c=_c("#FFFFFF"), a3c=_c("#FFD600"), a3a="\\3a&HC8&", aex="\\1a&H00&",
        ),
        # ── 12 Spaced Impact ──
        # UPPERCASE, 8px spacing. Inactive: 22% opacity. Active: white.
        "spaced_impact": dict(
            font="Montserrat-Black", sz=brd(52), bold=-1, italic=0, upper=True,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=brd(8),
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&HC8&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&",
        ),
        # ── 13 Ghost Pill ──
        # Inactive: 35% opacity. Active: white + capsule border.
        "ghost_pill": dict(
            font="Montserrat-Bold", sz=brd(52), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H96&",
            a1c=_c("#FFFFFF"), a3c=_c("#FFFFFF"), a3a="\\3a&H28&",
            aex="\\1a&H00&\\bord" + str(brd(2)) + "\\bs1",
        ),
        # ── 14 Documentary Tag ──
        # Bottom-left, italic Playfair. Inactive: 40% opacity. Active: warm cream.
        "documentary_tag": dict(
            font="PlayfairDisplay-Bold", sz=brd(48), bold=-1, italic=1, upper=False,
            an=1, px=bl_x, py=by, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H66&",
            a1c=_c("#F5E6C8"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&",
        ),
        # ── 15 Feather Light ──
        # NunitoSans, 1px spacing. Inactive: 32% opacity. Active: white + bold weight.
        "feather_light": dict(
            font="NunitoSans-Regular", sz=brd(50), bold=0, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=brd(1),
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&HAE&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\b1",
        ),
        # ── 16 Stroked Uppercase ──
        # UPPERCASE. Inactive: white + 3px stroke. Active: pink + same stroke.
        "stroked_uppercase": dict(
            font="Montserrat-Black", sz=brd(58), bold=-1, italic=0, upper=True,
            an=5, px=cx, py=cy, bs=1, ol=brd(3), shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="", iex="",
            a1c=_c("#FF3CAC"), a3c=_c("#000000"), a3a="", aex="",
        ),
        # ── 17 Accent Line ──
        # Inactive: 35% opacity. Active: white + underline.
        "accent_line": dict(
            font="Montserrat-Bold", sz=brd(52), bold=-1, italic=0, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=0,
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&H96&",
            a1c=_c("#FFFFFF"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\u1",
        ),
        # ── 18 Warm Serif Glow ──
        # Italic, 1px spacing. Inactive: 32% opacity. Active: warm cream + scale 1.08.
        "warm_serif_glow": dict(
            font="PlayfairDisplay-Bold", sz=brd(54), bold=-1, italic=1, upper=False,
            an=5, px=cx, py=cy, bs=1, ol=0, shad=0, sp=brd(1),
            i1c=_c("#FFFFFF"), i3c=_c("#000000"), i3a="\\3a&HFF&", iex="\\1a&HAE&",
            a1c=_c("#F5E0B0"), a3c=_c("#000000"), a3a="\\3a&HFF&", aex="\\1a&H00&\\fscx108\\fscy108",
        ),
    }
    return C.get(style_id, C["opus_classic"])


class CaptionCompositor:
    def __init__(self, style: CaptionStyle, width: int, height: int):
        self.style = style
        self.width = width
        self.height = height
        self.cfg = _get_config(style.style_id, width, height)

    def _build_ass(self, segments: List[CaptionSegment]) -> str:
        c = self.cfg
        font = c["font"]
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.width}
PlayResY: {self.height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{c['sz']},{_cs("#FFFFFF")},{_cs("#FFFFFF")},{_cs("#000000")},{_cs("#000000", 128)},{c['bold']},{c['italic']},0,0,100,100,{c['sp']},0,{c['bs']},{c['ol']},{c['shad']},{c['an']},20,20,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for seg in segments:
            words = seg.words
            if not words:
                continue
            for wi in range(len(words)):
                start = _t(words[wi].start_ms)
                end = _t(words[wi].end_ms)
                pos_tag = f"\\an{c['an']}\\pos({c['px']},{c['py']})"
                parts = [f"{{{pos_tag}}}"]
                for j, w in enumerate(words):
                    ws = _esc(w.word.upper() if c.get("upper") else w.word)
                    if j == wi:
                        tags = f"\\1c{c['a1c']}\\3c{c['a3c']}{c['a3a']}{c.get('aex', '')}"
                    else:
                        tags = f"\\1c{c['i1c']}\\3c{c['i3c']}{c['i3a']}{c.get('iex', '')}"
                    sep = " " if j < len(words) - 1 else ""
                    parts.append(f"{{{tags}}}{ws}{sep}")
                text = "".join(parts)
                events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        return header + "\n".join(events) + "\n"

    def composite_captions(self, input_video: str, output_video: str, segments: List[CaptionSegment]) -> dict:
        t0 = time.perf_counter()
        ass_content = self._build_ass(segments)

        ass_fd, ass_path = tempfile.mkstemp(suffix=".ass", prefix="nexcap_")
        try:
            with os.fdopen(ass_fd, "w", encoding="utf-8") as f:
                f.write(ass_content)

            ffmpeg = get_ffmpeg_path()
            ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
            fonts_escaped = FONTS_DIR.replace("\\", "/").replace(":", "\\:")

            cmd = [
                ffmpeg, "-y", "-i", input_video,
                "-vf", f"subtitles='{ass_escaped}':fontsdir='{fonts_escaped}'",
                "-c:v", "h264_nvenc", "-cq", "20", "-preset", "p6",
                "-c:a", "copy",
                output_video,
            ]
            logger.info(f"Compositing captions with style={self.style.style_id}")
            result = subprocess.run(cmd, capture_output=True, timeout=120)

            if result.returncode != 0:
                err = result.stderr.decode(errors="replace")[-400:]
                logger.error(f"FFmpeg failed: {err}")
                return {"success": False, "error": err}

            elapsed = time.perf_counter() - t0
            logger.info(f"Caption compositing SUCCESS → {output_video} in {elapsed:.1f}s")
            return {"success": True, "output_path": output_video, "style_id": self.style.style_id}
        finally:
            try:
                os.unlink(ass_path)
            except Exception:
                pass
