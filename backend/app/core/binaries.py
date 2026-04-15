"""
NexClip — External binary path resolution.
Finds yt-dlp, ffmpeg, ffprobe from the venv or system PATH.
"""

import os
import sys
import shutil
from pathlib import Path
from functools import lru_cache
from loguru import logger


@lru_cache(maxsize=1)
def get_ffmpeg_path() -> str:
    """Find ffmpeg binary — venv Scripts, imageio-ffmpeg, or system PATH."""
    # 1. Check venv Scripts
    venv_bin = Path(sys.executable).parent / "ffmpeg.exe"
    if venv_bin.exists():
        return str(venv_bin)
    venv_bin = Path(sys.executable).parent / "ffmpeg"
    if venv_bin.exists():
        return str(venv_bin)

    # 2. Try imageio-ffmpeg (Python-embedded ffmpeg)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and Path(path).exists():
            logger.info(f"Using imageio-ffmpeg: {path}")
            return path
    except ImportError:
        pass

    # 3. Fall back to system PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    raise FileNotFoundError(
        "ffmpeg not found. Install it with: pip install imageio-ffmpeg"
    )


@lru_cache(maxsize=1)
def get_ffprobe_path() -> str:
    """Find ffprobe binary."""
    # ffprobe is typically in the same directory as ffmpeg
    ffmpeg = get_ffmpeg_path()
    ffprobe = Path(ffmpeg).parent / "ffprobe.exe"
    if ffprobe.exists():
        return str(ffprobe)
    ffprobe = Path(ffmpeg).parent / "ffprobe"
    if ffprobe.exists():
        return str(ffprobe)
    found = shutil.which("ffprobe")
    if found:
        return found
    # Fall back to ffmpeg with -i probe
    return ""


@lru_cache(maxsize=1)
def get_yt_dlp_path() -> str:
    """Find yt-dlp binary — prefer the one in our venv's Scripts dir."""
    # Check venv Scripts directory first
    venv_bin = Path(sys.executable).parent / "yt-dlp.exe"
    if venv_bin.exists():
        return str(venv_bin)
    venv_bin = Path(sys.executable).parent / "yt-dlp"
    if venv_bin.exists():
        return str(venv_bin)
    # Fall back to system PATH
    found = shutil.which("yt-dlp")
    if found:
        return found
    raise FileNotFoundError(
        "yt-dlp not found. Install it with: pip install yt-dlp"
    )


def ensure_binaries_on_path() -> None:
    """
    Ensure ffmpeg, yt-dlp, etc. are on os.environ['PATH'].
    This is critical for third-party libraries like openai-whisper
    that internally call 'ffmpeg' via subprocess without accepting a path argument.
    """
    dirs_to_add = set()

    try:
        ffmpeg = get_ffmpeg_path()
        ffmpeg_dir = str(Path(ffmpeg).parent)
        dirs_to_add.add(ffmpeg_dir)
    except FileNotFoundError:
        pass

    try:
        yt_dlp = get_yt_dlp_path()
        yt_dlp_dir = str(Path(yt_dlp).parent)
        dirs_to_add.add(yt_dlp_dir)
    except FileNotFoundError:
        pass

    current_path = os.environ.get("PATH", "")
    for d in dirs_to_add:
        if d not in current_path:
            os.environ["PATH"] = d + os.pathsep + current_path
            current_path = os.environ["PATH"]
            logger.info(f"Added to PATH: {d}")


# Auto-inject at import time so all subprocess calls can find binaries
ensure_binaries_on_path()
