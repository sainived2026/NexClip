"""
NexClip — Caption Pipeline
End-to-end orchestrator for applying caption styles to clips.
"""

import os
import time
import logging
import subprocess
from typing import List, Dict, Any, Optional

from app.captions.models import CaptionWord, CaptionSegment, CaptionStyle
from app.captions.style_registry import get_style, get_all_styles
from app.core.binaries import get_ffprobe_path

logger = logging.getLogger(__name__)


def _get_video_dimensions(video_path: str) -> tuple:
    """Get video dimensions using ffprobe."""
    try:
        import json
        ffprobe = get_ffprobe_path()
        cmd = [
            ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(result.stdout)
        stream = info["streams"][0]
        return int(stream["width"]), int(stream["height"])
    except Exception:
        return 1080, 1920


def parse_word_timestamps(word_data: List[Dict]) -> List[CaptionSegment]:
    """
    Parse word-level timestamps into CaptionSegments.
    Preserves exact word-level timing from Whisper transcription.

    Args:
        word_data: List of dicts with {word, start, end} (times in seconds)

    Returns:
        List of CaptionSegments grouped into ~3-5 word phrases
    """
    if not word_data:
        return []

    words = []
    for wd in word_data:
        words.append(CaptionWord(
            word=wd.get("word", wd.get("text", "")),
            start_ms=int(wd.get("start", 0) * 1000),
            end_ms=int(wd.get("end", 0) * 1000),
            confidence=wd.get("confidence", 1.0),
        ))

    # Group into segments of ~4 words
    segments = []
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        if not chunk:
            continue
        segments.append(CaptionSegment(
            words=chunk,
            segment_start_ms=chunk[0].start_ms,
            segment_end_ms=chunk[-1].end_ms,
            text=" ".join(w.word for w in chunk),
        ))

    return segments


def apply_caption_style(
    input_video_path: str,
    word_timestamps: List[Dict],
    style_id: str,
    output_path: str,
    progress_callback=None,
) -> dict:
    """
    Apply a caption style to a video clip using FFmpeg ASS subtitles.
    Preserves exact word-level timing accuracy from Whisper.

    Args:
        input_video_path: Path to input video
        word_timestamps: Word-level timestamps [{word, start, end}, ...]
        style_id: Caption style ID
        output_path: Path for output video
        progress_callback: Optional callable(pct, msg)

    Returns:
        { success, output_path, style_id, segments_count }
    """
    t0 = time.perf_counter()

    if progress_callback:
        progress_callback(10, "Loading caption style...")

    style = get_style(style_id)
    if not style:
        logger.error(f"Unknown caption style: {style_id}")
        return {"success": False, "error": f"Unknown style: {style_id}"}

    if progress_callback:
        progress_callback(20, "Parsing word timestamps...")

    segments = parse_word_timestamps(word_timestamps)
    if not segments:
        logger.warning("No word timestamps to render captions for")
        return {"success": False, "error": "No word timestamps provided"}

    logger.info(
        f"Applying caption style '{style.display_name}' to {input_video_path} "
        f"({len(segments)} segments, {sum(len(s.words) for s in segments)} words)"
    )

    if progress_callback:
        progress_callback(30, f"Rendering {len(segments)} caption segments...")

    # Detect video dimensions using ffprobe
    width, height = _get_video_dimensions(input_video_path)

    # Use the ASS compositor for cinema-quality libass font rendering
    from app.captions.compositor import CaptionCompositor
    compositor = CaptionCompositor(style, width, height)

    if progress_callback:
        progress_callback(50, "Burning captions via FFmpeg ASS engine...")

    result = compositor.composite_captions(input_video_path, output_path, segments)

    elapsed = time.perf_counter() - t0
    result["elapsed_seconds"] = round(elapsed, 1)

    if progress_callback:
        progress_callback(100, "Caption rendering complete!")

    logger.info(f"ASS pipeline completed in {elapsed:.1f}s — success={result.get('success')}")
    return result
