"""
NexClip — Transcription Service v2.0
STT Fallback Chain: ElevenLabs → Local Faster-Whisper (GPU-first, CPU fallback)
Returns timestamped transcript as structured JSON.

Features:
  - Real-time progress reporting (percentage updates to DB)
  - GPU compatibility validation (detects Blackwell/sm_120 incompatibility)
  - Segment-by-segment progress logging
"""

import json
import subprocess
import time
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from loguru import logger

from app.core.config import get_settings
from app.core.binaries import get_ffmpeg_path
from app.services.storage_service import get_storage

settings = get_settings()
_local_whisper_gate = threading.BoundedSemaphore(
    value=max(1, int(getattr(settings, "WHISPER_MAX_PARALLEL_JOBS", 1)))
)

# Progress callback type: (percent: int, message: str) -> None
ProgressCallback = Optional[Callable[[int, str], None]]


class TranscriptionService:
    """Handles audio extraction and speech-to-text transcription."""

    def __init__(self):
        self.storage = get_storage()
        self.ffmpeg_bin = get_ffmpeg_path()
        logger.info(f"TranscriptionService ffmpeg: {self.ffmpeg_bin}")

    def extract_audio(self, video_path: str, output_path: str) -> str:
        """Extract audio from video using FFmpeg."""
        abs_video = self.storage.get_absolute_path(video_path)
        abs_audio = self.storage.get_absolute_path(output_path)

        Path(abs_audio).parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_bin, "-i", abs_video,
            "-vn",                      # No video
            "-acodec", "pcm_s16le",     # WAV format for Whisper compatibility
            "-ar", "16000",             # 16kHz sample rate
            "-ac", "1",                 # Mono
            "-y",                       # Overwrite
            abs_audio,
        ]

        logger.info(f"Extracting audio: {abs_video} → {abs_audio}")
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=settings.FFMPEG_AUDIO_TIMEOUT,
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg audio extraction failed: {result.stderr}")
            raise RuntimeError(f"Audio extraction failed: {result.stderr[:500]}")

        return output_path

    def _load_audio_with_ffmpeg(self, audio_path: str):
        """
        Load audio as numpy float32 array at 16kHz mono using our resolved ffmpeg.
        This replaces Whisper's built-in load_audio() which fails on Windows
        in Celery workers because it calls bare "ffmpeg" via subprocess.
        """
        import numpy as np

        cmd = [
            self.ffmpeg_bin,
            "-nostdin",
            "-threads", "0",
            "-i", audio_path,
            "-f", "s16le",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-"
        ]
        logger.info(f"Loading audio with ffmpeg: {self.ffmpeg_bin}")
        result = subprocess.run(
            cmd, capture_output=True,
            timeout=settings.AUDIO_LOAD_TIMEOUT,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to load audio: {result.stderr.decode()[:500]}")

        return np.frombuffer(result.stdout, np.int16).flatten().astype(np.float32) / 32768.0

    def _transliterate_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply Devanagari→Roman transliteration to all transcript segments.
        Uses the dedicated RomanizationService for accurate, word-boundary-aware conversion.
        """
        from app.services.romanization_service import RomanizationService
        return RomanizationService.transliterate_segments(segments)

    def _get_audio_duration_seconds(self, audio_path: str) -> float:
        """Get audio file duration in seconds."""
        cmd = [self.ffmpeg_bin, "-i", audio_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        import re
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
        if match:
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + float(f"0.{ms}")
        return 0.0

    def transcribe(
        self,
        audio_path: str,
        on_progress: ProgressCallback = None,
    ) -> List[Dict[str, Any]]:
        """
        Transcribe audio using the STT fallback chain:
        1. ElevenLabs (if API key configured)
        2. Local Whisper (GPU-first with compatibility check, CPU fallback)

        Post-processing: Devanagari → Roman transliteration for captions.
        """
        segments = None
        if settings.has_elevenlabs:
            try:
                logger.info("Attempting transcription via ElevenLabs STT")
                if on_progress:
                    on_progress(32, "Transcribing via ElevenLabs cloud STT...")
                segments = self._transcribe_elevenlabs(audio_path)
            except Exception as e:
                logger.warning(f"ElevenLabs STT failed: {e} — falling back to local Whisper")

        if segments is None:
            # Fallback: Local Whisper
            segments = self._transcribe_local(audio_path, on_progress=on_progress)

        # Post-process: transliterate any Devanagari to Roman script
        if on_progress:
            on_progress(48, "Post-processing transcript (transliteration)...")
        segments = self._transliterate_segments(segments)

        return segments

    def _transcribe_elevenlabs(self, audio_path: str) -> List[Dict[str, Any]]:
        """Transcribe using ElevenLabs Speech-to-Text API."""
        from elevenlabs import ElevenLabs

        abs_path = self.storage.get_absolute_path(audio_path)
        logger.info(f"Transcribing via ElevenLabs ({settings.ELEVENLABS_STT_MODEL}): {abs_path}")

        client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

        with open(abs_path, "rb") as audio_file:
            response = client.speech_to_text.convert(
                file=audio_file,
                model_id=settings.ELEVENLABS_STT_MODEL,
                tag_audio_events=False,
                # NOTE: language_code removed intentionally!
                # Hardcoding "en" was forcing English-only transcription on Hindi audio,
                # producing garbled romanization. ElevenLabs auto-detects language
                # when no code is specified — much more accurate for multilingual content.
            )

        segments = []
        if hasattr(response, "words") and response.words:
            # Group words into sentence-level segments
            current_segment = {"start": 0.0, "end": 0.0, "text": ""}
            word_count = 0

            for word in response.words:
                word_start = getattr(word, "start", 0) or 0
                word_end = getattr(word, "end", 0) or 0
                word_text = getattr(word, "text", "") or ""

                if not current_segment["text"]:
                    current_segment["start"] = round(word_start, 2)

                current_segment["text"] += word_text + " "
                current_segment["end"] = round(word_end, 2)
                word_count += 1

                # Split on sentence boundaries or every ~15 words
                is_sentence_end = word_text.rstrip().endswith((".", "!", "?", "...", "—"))
                if is_sentence_end or word_count >= 15:
                    segments.append({
                        "start": current_segment["start"],
                        "end": current_segment["end"],
                        "text": current_segment["text"].strip(),
                    })
                    current_segment = {"start": 0.0, "end": 0.0, "text": ""}
                    word_count = 0

            # Flush remaining words
            if current_segment["text"].strip():
                segments.append({
                    "start": current_segment["start"],
                    "end": current_segment["end"],
                    "text": current_segment["text"].strip(),
                })
        elif hasattr(response, "text") and response.text:
            # Fallback: single segment with full text
            segments.append({
                "start": 0.0,
                "end": 0.0,
                "text": response.text.strip(),
            })

        logger.info(f"ElevenLabs transcription complete: {len(segments)} segments")
        return segments

    def _check_gpu_compatibility(self) -> Dict[str, Any]:
        """
        Check if the GPU is actually compatible with the installed PyTorch.
        Instead of hardcoding supported compute capabilities, we actually
        run a tensor operation on GPU to verify it works.
        """
        import torch

        result = {
            "cuda_available": torch.cuda.is_available(),
            "can_use_gpu": False,
            "device_name": "none",
            "compute_capability": (0, 0),
            "pytorch_version": torch.__version__,
            "cuda_version": getattr(torch.version, "cuda", "none"),
            "reason": "",
        }

        if not torch.cuda.is_available():
            result["reason"] = "CUDA not available"
            return result

        result["device_name"] = torch.cuda.get_device_name(0)
        result["compute_capability"] = torch.cuda.get_device_capability(0)

        # Actually try a GPU operation — this is the only reliable test
        try:
            test = torch.zeros(1, device="cuda")
            _ = test + 1
            del test
            torch.cuda.empty_cache()
            result["can_use_gpu"] = True
            result["reason"] = "GPU verified working"
        except Exception as e:
            major, minor = result["compute_capability"]
            result["reason"] = (
                f"GPU {result['device_name']} (sm_{major}{minor}) failed compute test: {e}. "
                f"PyTorch {torch.__version__} (CUDA {torch.version.cuda}) may not support this GPU. "
                f"Using CPU instead."
            )
            logger.warning(f"⚠️ GPU test failed: {e}")

        return result

    @contextmanager
    def _local_transcription_slot(self, on_progress: ProgressCallback = None):
        waiting_logged = False
        while True:
            acquired = _local_whisper_gate.acquire(timeout=1)
            if acquired:
                break
            if on_progress and not waiting_logged:
                on_progress(
                    32,
                    "Waiting for the local Whisper slot. Another long transcription is already running...",
                )
            if not waiting_logged:
                logger.warning("Local Whisper slot busy; waiting for the active transcription to finish.")
                waiting_logged = True
        try:
            yield
        finally:
            _local_whisper_gate.release()

    def _transcribe_local(
        self,
        audio_path: str,
        on_progress: ProgressCallback = None,
    ) -> List[Dict[str, Any]]:
        """
        Transcribe using local Whisper model.
        GPU-first with Blackwell compatibility check, falls back to CPU if needed.
        Reports progress as percentage based on audio duration.
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("faster-whisper not installed. pip install faster-whisper")

        abs_path = self.storage.get_absolute_path(audio_path)
        logger.info(f"Transcribing locally with model '{settings.WHISPER_MODEL}': {abs_path}")

        with self._local_transcription_slot(on_progress=on_progress):
            audio_array = self._load_audio_with_ffmpeg(abs_path)
            audio_duration = len(audio_array) / 16000.0
            logger.info(f"Audio duration: {audio_duration:.1f}s ({audio_duration/60:.1f} minutes)")

            if on_progress:
                on_progress(33, f"Audio loaded ({audio_duration/60:.0f} min). Checking GPU compatibility...")

            gpu_info = self._check_gpu_compatibility()
            logger.info(f"GPU check: {gpu_info['reason']}")

            if gpu_info["can_use_gpu"]:
                device = settings.WHISPER_DEVICE
                compute_type = settings.WHISPER_COMPUTE_TYPE
                logger.info(
                    f"Using GPU: {gpu_info['device_name']} "
                    f"(sm_{gpu_info['compute_capability'][0]}{gpu_info['compute_capability'][1]}, {compute_type})"
                )
                if on_progress:
                    on_progress(34, f"Using GPU: {gpu_info['device_name']} - loading Whisper model...")
            else:
                device = "cpu"
                compute_type = "int8"
                logger.warning(
                    f"GPU not usable ({gpu_info['reason']}). "
                    f"Falling back to CPU with int8 quantization. "
                    f"This will be slower for long audio."
                )
                if on_progress:
                    on_progress(34, "GPU incompatible - using CPU (int8). This may take longer...")

            global _whisper_model_cache
            if "_whisper_model_cache" not in globals():
                _whisper_model_cache = None

            if _whisper_model_cache is None:
                model_load_start = time.perf_counter()
                _whisper_model_cache = WhisperModel(
                    settings.WHISPER_MODEL,
                    device=device,
                    compute_type=compute_type,
                )
                model_load_time = time.perf_counter() - model_load_start
                logger.info(
                    f"Whisper model loaded in {model_load_time:.1f}s "
                    f"(device={device}, compute={compute_type})"
                )
            else:
                logger.info("Using cached Whisper model.")

            model = _whisper_model_cache

            if on_progress:
                on_progress(35, "Whisper model ready. Starting transcription...")

            transcribe_start = time.perf_counter()
            segments_gen, info = model.transcribe(audio_array, beam_size=5)

            logger.info(
                f"Detected language: '{info.language}' (probability {info.language_probability:.2f}). "
                f"Audio duration: {info.duration:.0f}s"
            )

            total_duration = info.duration if info.duration > 0 else audio_duration
            segments = []
            last_progress_pct = 35
            last_log_time = time.perf_counter()

            for seg in segments_gen:
                segments.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })

                if total_duration > 0:
                    seg_pct = min(seg.end / total_duration, 1.0)
                    current_pct = 35 + int(seg_pct * 13)
                else:
                    current_pct = 35

                now = time.perf_counter()
                if current_pct > last_progress_pct or (now - last_log_time) >= 10:
                    elapsed = now - transcribe_start
                    if seg.end > 0 and total_duration > 0:
                        speed = seg.end / elapsed if elapsed > 0 else 0
                        remaining_audio = total_duration - seg.end
                        eta_seconds = remaining_audio / speed if speed > 0 else 0
                        eta_str = f"{eta_seconds/60:.0f}min" if eta_seconds > 60 else f"{eta_seconds:.0f}s"
                    else:
                        eta_str = "calculating..."

                    overall_pct = int((seg.end / total_duration * 100) if total_duration > 0 else 0)
                    logger.info(
                        f"STT Progress: {overall_pct}% done "
                        f"({seg.end:.0f}s / {total_duration:.0f}s) | "
                        f"{len(segments)} segments | ETA: {eta_str}"
                    )

                    if on_progress and current_pct > last_progress_pct and total_duration > 0:
                        on_progress(
                            current_pct,
                            f"Transcribing: {overall_pct}% ({seg.end:.0f}s/{total_duration:.0f}s) - ETA: {eta_str}",
                        )

                    last_progress_pct = current_pct
                    last_log_time = now

            total_time = time.perf_counter() - transcribe_start
            speed_ratio = total_duration / total_time if total_time > 0 else 0
            logger.info(
                f"Transcription complete: {len(segments)} segments in {total_time:.1f}s "
                f"({speed_ratio:.1f}x realtime) | Device: {device} | Model: {settings.WHISPER_MODEL}"
            )
            return segments

    def save_transcript(self, segments: List[Dict], project_folder: str) -> str:
        """Save transcript JSON to storage."""
        file_path = f"{project_folder}/transcript/transcript.json"
        abs_path = self.storage.get_absolute_path(file_path)
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)

        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)

        logger.info(f"Transcript saved: {file_path}")
        return file_path

    def get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds using FFmpeg (metadata read only)."""
        abs_path = self.storage.get_absolute_path(video_path)
        cmd = [self.ffmpeg_bin, "-i", abs_path]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=settings.FFMPEG_DURATION_TIMEOUT,
        )
        # Parse "Duration: HH:MM:SS.ms" from stderr
        import re
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
        if match:
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + float(f"0.{ms}")
        return 0.0
