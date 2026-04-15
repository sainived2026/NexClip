"""
NexClip — YouTube / URL Download Service
Uses yt-dlp to safely download video from YouTube and public URLs.
All timeouts come from .env via Settings.
"""

import uuid
import subprocess
from pathlib import Path
from typing import Dict, Any
from loguru import logger

from app.core.config import get_settings
from app.core.binaries import get_yt_dlp_path
from app.services.storage_service import get_storage

settings = get_settings()


def _resolve_cookie_file() -> Path | None:
    """
    Find a usable `cookies.txt` regardless of the current working directory.
    """
    backend_root = Path(__file__).resolve().parents[2]
    repo_root = backend_root.parent
    candidates = [
        Path.cwd() / "cookies.txt",
        backend_root / "cookies.txt",
        repo_root / "cookies.txt",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


class DownloadService:
    """Downloads videos from YouTube and public URLs using yt-dlp."""

    def __init__(self):
        self.storage = get_storage()
        self.yt_dlp_bin = get_yt_dlp_path()
        logger.info(f"DownloadService using yt-dlp at: {self.yt_dlp_bin}")

    def download_video(self, url: str, project_folder: str) -> Dict[str, Any]:
        """
        Download video from URL. Returns dict with file_path, filename, duration.
        Timeout from settings.DOWNLOAD_TIMEOUT.
        """
        output_dir = f"{project_folder}/upload"
        abs_dir = self.storage.get_absolute_path(output_dir)
        Path(abs_dir).mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.mp4"
        abs_output = str(Path(abs_dir) / filename)

        import sys
        base_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--format", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "--output", abs_output,
            "--no-playlist",
            "--no-warnings",
            "--no-progress",
            "--socket-timeout", "30",
            "--retries", "5",
            "--extractor-retries", "3",
            # Removed static --user-agent to allow yt-dlp to match the browser's User-Agent perfectly
        ]

        import yt_dlp

        browsers_to_try = [None]
        cookies_txt_path = _resolve_cookie_file()

        if cookies_txt_path:
            logger.info(f"Found cookies.txt file, will use it: {cookies_txt_path}")
            browsers_to_try.insert(0, "cookies.txt")

        if settings.YTDLP_COOKIES_BROWSER and settings.YTDLP_COOKIES_BROWSER.lower() != "none":
            browsers_to_try.insert(0, settings.YTDLP_COOKIES_BROWSER.lower())

        error_msg = ""
        success = False
        
        for browser in browsers_to_try:
            ydl_opts = {
                'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'outtmpl': abs_output,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 5,
                'extractor_retries': 3,
            }
            
            if browser == "cookies.txt" and cookies_txt_path:
                ydl_opts['cookiefile'] = str(cookies_txt_path)
            elif browser is not None:
                ydl_opts['cookiesfrombrowser'] = (browser,)
                
            try:
                logger.info(f"Attempting python yt-dlp download with cookies: '{browser}'")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                success = True
                logger.info(f"Successfully downloaded with '{browser}' via native API.")
                break
            except Exception as e:
                error_msg = str(e)
                # Windows file-lock: yt-dlp downloaded OK but can't rename .temp → .mp4
                if "being used by another process" in error_msg or "WinError 32" in error_msg:
                    import time as _time
                    import gc
                    gc.collect()  # Release any dangling file handles
                    # Try to find and rename the temp file ourselves
                    temp_pattern = Path(abs_dir).glob("*.temp.mp4")
                    for temp_file in temp_pattern:
                        target = temp_file.with_suffix("").with_suffix(".mp4") if ".temp.mp4" in temp_file.name else Path(abs_output)
                        for attempt in range(5):
                            try:
                                _time.sleep(0.5 * (attempt + 1))
                                if temp_file.exists():
                                    temp_file.rename(target)
                                    abs_output = str(target)
                                    filename = target.name
                                    success = True
                                    logger.info(f"Renamed temp file on attempt {attempt + 1}")
                                    break
                            except OSError:
                                continue
                        if success:
                            break
                    # If rename failed but the output file already exists (another thread renamed it)
                    if not success and Path(abs_output).exists():
                        success = True
                        logger.info("Output file already exists despite rename error")
                    if success:
                        break
                logger.warning(f"Native yt-dlp attempt '{browser}' failed: {error_msg}")
                if "Video unavailable" in error_msg and "confirm you're not a bot" not in error_msg:
                    break
                    
        if not success:
            clean_err = f"Download failed: {error_msg}"
            if "confirm you're not a bot" in error_msg:
                  clean_err = (
                      "YouTube bot detection blocked the server download. "
                      "Provide a valid cookies export at backend/cookies.txt "
                      "or configure a working browser profile for yt-dlp on the server."
                  )
            raise RuntimeError(clean_err)

        # Verify file exists
        if not Path(abs_output).exists():
            # yt-dlp sometimes appends extension — find the file
            for f in Path(abs_dir).glob(f"{filename.rsplit('.', 1)[0]}*"):
                abs_output = str(f)
                filename = f.name
                break
            else:
                raise RuntimeError("Downloaded file not found")

        file_path = f"{output_dir}/{filename}"
        file_size = Path(abs_output).stat().st_size

        logger.info(f"Download complete: {file_path} ({file_size} bytes)")
        return {
            "file_path": file_path,
            "filename": filename,
            "file_size": file_size,
        }

    def validate_url(self, url: str) -> bool:
        """Basic URL validation."""
        if not url or len(url) < 10:
            return False
        if not url.startswith(("http://", "https://")):
            return False
        return True
