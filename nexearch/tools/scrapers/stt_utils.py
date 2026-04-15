"""
nexearch/tools/scrapers/stt_utils.py
Best-effort Speech-to-Text helper.
Tries the NexClip TranscriptionService first, then falls back to yt-dlp + faster-whisper.
Returns an empty string on any failure — never raises.
"""

from __future__ import annotations

import os
import tempfile
from loguru import logger


def transcribe_scraped_post(video_url: str) -> str:
    """
    Transcribe a video URL to plain text.
    Returns empty string on any error.
    """
    if not video_url or not video_url.startswith(("http://", "https://")):
        return ""

    # ── Strategy 1: NexClip backend TranscriptionService ─────────────────────
    try:
        from app.services.download_service import DownloadService
        from app.services.transcription_service import TranscriptionService

        dl   = DownloadService()
        svc  = TranscriptionService()
        path = dl.download_video(video_url)
        if path and os.path.exists(path):
            result = svc.transcribe_video(path)
            text   = (result or {}).get("text", "")
            try:
                os.remove(path)
            except Exception:
                pass
            if text:
                logger.debug(f"[STT] TranscriptionService succeeded for {video_url[:60]}")
                return text
    except Exception as e:
        logger.debug(f"[STT] TranscriptionService unavailable: {e}")

    # ── Strategy 2: yt-dlp + faster-whisper (optional, local GPU) ─────────────
    try:
        import yt_dlp
        from faster_whisper import WhisperModel  # type: ignore

        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, "vid.%(ext)s")
            ydl_opts = {
                "format":      "bestaudio/best",
                "outtmpl":     outtmpl,
                "quiet":       True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            audio_files = [f for f in os.listdir(tmpdir) if f.startswith("vid.")]
            if not audio_files:
                return ""

            audio_path = os.path.join(tmpdir, audio_files[0])
            model = WhisperModel("base", device="auto", compute_type="int8")
            segments, _ = model.transcribe(audio_path, beam_size=2)
            text = " ".join(seg.text for seg in segments).strip()
            if text:
                logger.debug(f"[STT] faster-whisper succeeded for {video_url[:60]}")
            return text
    except Exception as e:
        logger.debug(f"[STT] faster-whisper fallback failed: {e}")

    return ""
