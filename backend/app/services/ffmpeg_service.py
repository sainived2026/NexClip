"""
NexClip — Cinematic Camera Director (FFmpeg Clip Generation Service)
Enterprise-grade clip generation with OpusClip-grade visual quality.

Architecture:
1. Complex Filter Graph — Blurred BG + Sharp Speaker Crop + Overlay
2. Bézier-Eased Camera Tracking — Smoothstep interpolation (3t²-2t³)
3. Rule-of-Thirds Smart Framing — Professional portrait composition
4. Parallel Clip Generation — ThreadPoolExecutor for vCore utilization
5. Enhanced Caption System — Semi-transparent box, centered, fade-ready

Filter Graph Pipeline:
┌─────────────────────────────────────────────────┐
│  [0:v] ─── blur+scale ──→ [bg]                  │  Background layer
│  [0:v] ─── smartcrop+scale ──→ [fg]              │  Speaker crop
│  [bg][fg] ─── overlay(center) ──→ [composed]     │  Layered composition
│  [composed] ─── drawtext ──→ [vout]              │  Caption burn-in
└─────────────────────────────────────────────────┘
"""

import os
import json
import subprocess
import uuid
import re as _re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
import numpy as np

from app.core.config import get_settings
from app.core.binaries import get_ffmpeg_path, get_ffprobe_path
from app.services.storage_service import get_storage
from app.services.speaker_detection_service import get_speaker_detection_service, SpeakerKeyframe

settings = get_settings()


class FFmpegService:
    """Handles all video cutting, cropping, and caption overlay operations with speaker focus."""

    def __init__(self):
        self.storage = get_storage()
        self.ffmpeg_bin = get_ffmpeg_path()
        self.ffprobe_bin = get_ffprobe_path()
        self.output_width = settings.OUTPUT_VIDEO_WIDTH
        self.output_height = settings.OUTPUT_VIDEO_HEIGHT
        logger.info(f"FFmpegService using: {self.ffmpeg_bin} (output: {self.output_width}x{self.output_height})")

    def _get_video_dimensions(self, video_path: str) -> Tuple[int, int]:
        """Get source video width and height using ffprobe."""
        abs_path = self.storage.get_absolute_path(video_path)
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            abs_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            info = json.loads(result.stdout)
            stream = info["streams"][0]
            w = int(stream["width"])
            h = int(stream["height"])
            logger.debug(f"Video dimensions: {w}x{h}")
            return w, h
        except Exception as e:
            logger.warning(f"ffprobe failed ({e}), defaulting to 1920x1080")
            return 1920, 1080

    def generate_clip(
        self,
        video_path: str,
        clip_data: Dict[str, Any],
        project_folder: str,
        src_dimensions: Tuple[int, int] = None,
        preset_id: str = "youtube_bold",
        include_scfs_metadata: bool = False,
    ) -> str | Dict[str, Any]:
        """
        Generate a single clip using MediaPipe FaceMesh speaker detection
        + FFmpeg complex filter graphs (Bézier-eased cinematic tracking).

        This is the FAST path: single FFmpeg pass, ~10s per clip.
        """
        abs_video = self.storage.get_absolute_path(video_path)
        start = clip_data["start"]
        end = clip_data["end"]
        rank = clip_data.get("rank", 1)
        duration = end - start

        # Output path
        output_dir = f"{project_folder}/clip"
        output_filename = f"clip_{rank:02d}_{uuid.uuid4().hex[:8]}.mp4"
        output_rel = f"{output_dir}/{output_filename}"
        abs_output = self.storage.get_absolute_path(output_rel)
        Path(abs_output).parent.mkdir(parents=True, exist_ok=True)

        # Get source video dimensions (use pre-fetched if available)
        if src_dimensions:
            src_width, src_height = src_dimensions
        else:
            src_width, src_height = self._get_video_dimensions(video_path)

        # ── Active Speaker Detection (MediaPipe FaceMesh) ──
        t0 = time.perf_counter()
        speaker_service = get_speaker_detection_service()
        scfs_metadata = {
            "sfcs_version": "director_v4",
            "sfcs_faces_detected": 0,
            "sfcs_frames_with_speaker": 0,
            "sfcs_fallback_frames": 0,
        }

        try:
            detection_result = speaker_service.detect_active_speaker_with_metadata(
                video_path, start, duration, src_width, src_height
            )
            keyframes = detection_result.keyframes
            scfs_metadata.update(detection_result.to_clip_metadata())
        except Exception as e:
            logger.warning(f"Speaker detection failed for clip {rank}: {e}")
            keyframes = []

        # ── Build Cinematic Filter Graph ──
        filter_str, is_complex = self._build_cinematic_filter(
            start, end, src_width, src_height,
            keyframes=keyframes, preset_id=preset_id,
        )

        # ── Encode with FFmpeg ──
        cmd = [self.ffmpeg_bin, "-y"]
        cmd += ["-ss", str(start), "-i", abs_video, "-t", str(duration)]

        if is_complex:
            cmd += ["-filter_complex", filter_str, "-map", "[vout]", "-map", "0:a?"]
        else:
            cmd += ["-vf", filter_str]

        cmd += [
            "-c:v", settings.VIDEO_CODEC,
            "-preset", settings.VIDEO_PRESET,
            "-crf", str(settings.VIDEO_CRF),
            "-c:a", settings.AUDIO_CODEC,
            "-b:a", settings.AUDIO_BITRATE,
            "-ar", str(settings.AUDIO_SAMPLE_RATE),
            "-movflags", "+faststart",
            "-threads", str(settings.FFMPEG_THREADS_PER_CLIP),
            abs_output,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        encode_time = time.perf_counter() - t0

        if result.returncode != 0:
            logger.error(f"FFmpeg clip {rank} failed: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg encode failed for clip {rank}")

        logger.info(f"Clip {rank} generated in {encode_time:.1f}s: {output_rel}")
        if include_scfs_metadata:
            return {
                "output_path": output_rel,
                "scfs": scfs_metadata,
            }
        return output_rel

    # ── CINEMATIC FILTER ARCHITECTURE ──────────────────────────────

    def _build_cinematic_filter(
        self,
        clip_start: float,
        clip_end: float,
        src_width: int = 1920,
        src_height: int = 1080,
        keyframes: Optional[List[SpeakerKeyframe]] = None,
        preset_id: str = "youtube_bold",
    ) -> Tuple[str, bool]:
        """
        Build the cinematic filter chain.

        Architecture (when speaker detected):
        ┌───────────────────────────────────────┐
        │  [0:v] ─── blur+scale ──→ [bg]        │  Blurred background layer
        │  [0:v] ─── smartcrop ──→ [fg]          │  Sharp speaker-focused crop
        │  [bg][fg] ─── overlay ──→ [vout]       │  Layered composition
        └───────────────────────────────────────┘

        Returns: (filter_string, uses_complex_filter_graph)
        """
        out_w = self.output_width
        out_h = self.output_height
        target_ratio = out_w / out_h  # 9:16 = 0.5625
        src_ratio = src_width / src_height

        # Compute crop dimensions in source coordinates
        if src_ratio > target_ratio:
            crop_h = src_height
            crop_w = int(src_height * target_ratio)
        else:
            crop_w = src_width
            crop_h = int(src_width / target_ratio)

        has_speaker = keyframes and len(keyframes) >= 1

        if has_speaker:
            # ── CINEMATIC MODE: Blurred BG + Sharp Speaker Crop ──
            return self._build_complex_filter_graph(
                keyframes, crop_w, crop_h, src_width, src_height,
                src_ratio, target_ratio, out_w, out_h,
                clip_start, clip_end, preset_id
            ), True
        else:
            # ── FALLBACK: Simple center crop (no speaker) ──
            logger.info("No speaker detected — using center crop fallback")
            filters = []
            filters.append(f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase")
            filters.append(f"crop={out_w}:{out_h}")

            return ",".join(filters), False

    def _build_complex_filter_graph(
        self,
        keyframes: List[SpeakerKeyframe],
        crop_w: int,
        crop_h: int,
        src_width: int,
        src_height: int,
        src_ratio: float,
        target_ratio: float,
        out_w: int,
        out_h: int,
        clip_start: float,
        clip_end: float,
        preset_id: str = "youtube_bold",
    ) -> str:
        """
        Build a complex filter graph with:
        1. [bg] — Blurred, scaled background (the TikTok/Shorts look)
        2. [fg] — Sharp, speaker-focused crop with Bézier-eased tracking
        3. Overlay [fg] centered on [bg]


        This is the enterprise-grade filter architecture that makes
        NexClip clips look professional and polished.
        """
        # ── Layer 1: Blurred Background ──
        # Scale source to fill 9:16 output, then apply heavy Gaussian blur
        bg_filter = (
            f"[0:v]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
            f"crop={out_w}:{out_h},"
            f"boxblur=luma_radius=25:luma_power=2,"
            f"eq=brightness=-0.08[bg]"
        )

        # ── Layer 2: Sharp Speaker Crop with Dynamic Tracking ──
        fg_crop = self._build_speaker_crop_filter(
            keyframes, crop_w, crop_h, src_width, src_height,
            src_ratio, target_ratio, out_w, out_h,
        )

        # ── Layer 3: Overlay sharp crop onto blurred background ──
        # Center the sharp crop on the blurred background
        overlay_filter = "[bg][fg]overlay=(W-w)/2:(H-h)/2[vout]"

        # Assemble the complete filter graph
        graph = f"{bg_filter};{fg_crop};{overlay_filter}"

        logger.info(
            f"Cinematic filter graph: bg(blur) + fg(speaker crop) + overlay"
        )
        return graph

    def _build_speaker_crop_filter(
        self,
        keyframes: List[SpeakerKeyframe],
        crop_w: int,
        crop_h: int,
        src_width: int,
        src_height: int,
        src_ratio: float,
        target_ratio: float,
        out_w: int,
        out_h: int,
    ) -> str:
        """
        Build SMOOTH ANIMATED speaker crop. Outputs the [fg] stream.
        
        Cinematic Director paradigm:
        - Camera LOCKS during a speaker's turn (consecutive keyframes = same pos)
        - Camera SMOOTHLY GLIDES on speaker change (Bézier smoothstep)
        - This creates the exactly professional look of OpusClip
        """
        if not keyframes:
            cx = max(0, (src_width - crop_w) // 2)
            cy = max(0, (src_height - crop_h) // 2)
            return f"[0:v]crop={crop_w}:{crop_h}:{cx}:{cy},scale={out_w}:{out_h}[fg]"

        if len(keyframes) == 1:
            kf = keyframes[0]
            cx, cy = self._compute_smart_crop_position(
                kf, crop_w, crop_h, src_width, src_height, src_ratio, target_ratio
            )
            fg = f"[0:v]crop={crop_w}:{crop_h}:{cx}:{cy},scale={out_w}:{out_h}[fg]"
            logger.info(f"Single speaker lock at ({cx},{cy})")
            return fg

        # ── Multiple keyframes: Bézier smoothstep between positions ──
        # CRITICAL FIX: Convert ABSOLUTE timestamps to CLIP-RELATIVE.
        # FFmpeg's `t` variable starts at 0.0 for each clip (due to -ss seeking).
        # Keyframe timestamps are absolute video times (e.g., 542.0s).
        # We MUST subtract the first keyframe's time to make them relative.
        clip_start_time = keyframes[0].timestamp
        
        # Downsample if too many keyframes
        MAX_KF = 30
        if len(keyframes) > MAX_KF:
            step = (len(keyframes) - 1) / (MAX_KF - 1)
            indices = sorted(set(int(round(i * step)) for i in range(MAX_KF)))
            keyframes = [keyframes[i] for i in indices]

        positions_x = []
        positions_y = []

        for kf in keyframes:
            cx, cy = self._compute_smart_crop_position(
                kf, crop_w, crop_h, src_width, src_height, src_ratio, target_ratio
            )
            # Convert to clip-relative time (t=0.0 at clip start)
            rel_time = kf.timestamp - clip_start_time
            positions_x.append((rel_time, cx))
            positions_y.append((rel_time, cy))

        if src_ratio > target_ratio:
            # Landscape: smooth X with Bézier, stable Y=0 (full height preserved)
            x_expr = self._keyframes_to_bezier_expr(positions_x, src_width - crop_w)
            crop_expr = f"crop={crop_w}:{crop_h}:{x_expr}:0"
        else:
            # Portrait: smooth Y with Bézier, X=0
            y_expr = self._keyframes_to_bezier_expr(positions_y, src_height - crop_h)
            crop_expr = f"crop={crop_w}:{crop_h}:0:{y_expr}"

        fg_filter = f"[0:v]{crop_expr},scale={out_w}:{out_h}[fg]"
        logger.info(
            f"Smooth animated crop: {len(keyframes)} keyframes, Bézier-eased, "
            f"{crop_w}x{crop_h}, clip_start={clip_start_time:.1f}s"
        )
        return fg_filter

    def _compute_smart_crop_position(
        self,
        kf: SpeakerKeyframe,
        crop_w: int,
        crop_h: int,
        src_width: int,
        src_height: int,
        src_ratio: float,
        target_ratio: float,
    ) -> Tuple[int, int]:
        """
        Compute smart crop position for speaker-focused framing.

        For LANDSCAPE → PORTRAIT (most podcasts):
        - crop_h = src_height (full height preserved) → Y = 0 always
        - crop_w < src_width (narrow vertical strip) → X centers on face

        For PORTRAIT → PORTRAIT:
        - crop_w = src_width → X = 0 always
        - crop_h < src_height → Y positions face in upper third
        
        CRITICAL: The entire face bounding box (plus safety margin) MUST be
        contained within the crop window. This prevents face edges from being clipped.
        """
        # Safety margin: 20% of face width on each side
        face_margin_x = max(20, int(kf.face_width * 0.2))
        face_margin_y = max(15, int(kf.face_height * 0.2))
        
        if src_ratio > target_ratio:
            # ── LANDSCAPE SOURCE (16:9 → 9:16) ──
            # Full height is kept. Only X varies.
            # Center the crop window horizontally on the speaker's face.
            crop_x = kf.center_x - crop_w // 2

            # Add slight bias: if face is near left edge, don't cut off the face
            face_margin = max(kf.face_width, crop_w // 6)  # At least 1/6 crop width margin
            
            # ── Face bounding box containment ──
            # Ensure face left edge (with margin) is inside crop
            face_left = kf.center_x - kf.face_width // 2 - face_margin_x
            face_right = kf.center_x + kf.face_width // 2 + face_margin_x
            # If face left edge would be clipped, shift crop left
            if face_left < crop_x:
                crop_x = max(0, face_left)
            # If face right edge would be clipped, shift crop right
            if face_right > crop_x + crop_w:
                crop_x = min(src_width - crop_w, face_right - crop_w)

            crop_x = max(0, min(crop_x, src_width - crop_w))

            # Y = 0 because crop_h = src_height (full height preserved)
            crop_y = 0
            
            logger.debug(
                f"Landscape crop: face_cx={kf.center_x}, crop_x={crop_x}, "
                f"crop={crop_w}x{crop_h}, Y=0 (full height)"
            )
        else:
            # ── PORTRAIT/SQUARE SOURCE ──
            # Full width is kept. Only Y varies.
            crop_x = 0

            # Rule-of-thirds: place face in upper 1/3 of crop
            if kf.face_top > 0 and kf.face_bottom > kf.face_top:
                # Place face_top at 20% of crop height from top
                headroom = int(crop_h * 0.20)
                crop_y = max(0, kf.face_top - headroom)
            else:
                # Fallback: center face at 1/3 from top
                crop_y = max(0, kf.center_y - int(crop_h * 0.33))
            
            # ── Face bounding box containment (vertical) ──
            face_top_bound = max(0, kf.face_top - face_margin_y)
            face_bottom_bound = min(src_height, kf.face_bottom + face_margin_y)
            if face_top_bound < crop_y:
                crop_y = max(0, face_top_bound)
            if face_bottom_bound > crop_y + crop_h:
                crop_y = min(src_height - crop_h, face_bottom_bound - crop_h)

        # Clamp to valid bounds
        crop_y = max(0, min(crop_y, src_height - crop_h))
        crop_x = max(0, min(crop_x, src_width - crop_w))

        return crop_x, crop_y

    # ── BÉZIER-EASED KEYFRAME INTERPOLATION ───────────────────────

    def _keyframes_to_bezier_expr(
        self,
        keyframes: List[Tuple[float, int]],
        max_val: int,
    ) -> str:
        """
        Convert keyframes into an FFmpeg expression with smoothstep easing.

        Uses the smoothstep function: f(t) = 3t² - 2t³
        This creates cinematic camera movement with natural acceleration
        at the start and deceleration at the end of each transition.

        Compared to linear interpolation (jittery, robotic feeling),
        smoothstep feels like a professional camera operator.
        """
        if not keyframes:
            return "0"
        if len(keyframes) == 1:
            return str(min(keyframes[0][1], max_val))

        # Build nested if() expression from last to first
        expr = str(min(keyframes[-1][1], max_val))

        for i in range(len(keyframes) - 2, -1, -1):
            t0, p0 = keyframes[i]
            t1, p1 = keyframes[i + 1]
            p0 = min(p0, max_val)
            p1 = min(p1, max_val)

            if abs(t1 - t0) < 0.01:
                lerp = str(p1)
            else:
                # Smoothstep: normalized_t = (t - t0) / (t1 - t0)
                # eased = 3*nt^2 - 2*nt^3
                # result = p0 + (p1 - p0) * eased
                nt = f"((t-{t0:.2f})/({t1:.2f}-{t0:.2f}))"
                # Clamp nt to [0,1]
                nt_clamped = f"clip({nt}\\,0\\,1)"
                # Smoothstep: 3t² - 2t³ = t*t*(3 - 2*t)
                eased = f"({nt_clamped}*{nt_clamped}*(3-2*{nt_clamped}))"
                lerp = f"{p0}+({p1}-{p0})*{eased}"

            clamped = f"clip({lerp}\\,0\\,{max_val})"
            expr = f"if(lt(t\\,{t1:.2f})\\,{clamped}\\,{expr})"

        return expr

    # ── PARALLEL CLIP GENERATION ───────────────────────────────────

    def generate_all_clips(
        self,
        video_path: str,
        clips_data: List[Dict[str, Any]],
        project_folder: str,
        progress_callback=None,
        on_clip_completed=None,
        preset_id: str = "youtube_bold",
    ) -> List[Dict[str, Any]]:
        """
        Generate all clips for a project using PARALLEL execution.
        Uses ThreadPoolExecutor to generate multiple clips concurrently,
        maximizing CPU utilization on multi-core VPS.
        """
        if not clips_data:
            return []

        # Pre-fetch video dimensions once (avoid N ffprobe calls)
        src_dimensions = self._get_video_dimensions(video_path)
        max_workers = settings.FFMPEG_PARALLEL_CLIPS
        total = len(clips_data)

        logger.info(
            f"Generating {total} clips in parallel "
            f"(max_workers={max_workers}, preset={settings.VIDEO_PRESET})"
        )

        results = [None] * total
        completed = 0

        def _generate_one(idx: int, clip_data: Dict) -> Tuple[int, Dict]:
            try:
                # 9:16 Cropped Clip
                render_result = self.generate_clip(
                    video_path, clip_data, project_folder,
                    src_dimensions=src_dimensions,
                    preset_id=preset_id,
                    include_scfs_metadata=True,
                )
                output_path = render_result["output_path"]
                clip_data["file_path"] = output_path
                clip_data.update(render_result.get("scfs", {}))
                
                # 16:9 Original Landscape Clip (Fast Trim)
                import uuid
                import subprocess
                from pathlib import Path
                
                rank = clip_data.get("rank", idx + 1)
                start = clip_data["start"]
                duration = clip_data["duration"]
                
                output_rel_16x9 = f"{project_folder}/clips/clip_{rank:02d}_{uuid.uuid4().hex[:8]}_16x9.mp4"
                abs_out_16x9 = self.storage.get_absolute_path(output_rel_16x9)
                Path(abs_out_16x9).parent.mkdir(parents=True, exist_ok=True)
                
                cmd_16x9 = [
                    self.ffmpeg_bin,
                    "-ss", str(start),
                    "-i", self.storage.get_absolute_path(video_path),
                    "-t", str(duration),
                    "-c:v", settings.VIDEO_CODEC,
                    "-preset", settings.VIDEO_PRESET,
                    "-crf", str(settings.VIDEO_CRF),
                    "-c:a", settings.AUDIO_CODEC,
                    "-b:a", settings.AUDIO_BITRATE,
                    "-ar", str(settings.AUDIO_SAMPLE_RATE),
                    "-movflags", "+faststart",
                    "-threads", str(settings.FFMPEG_THREADS_PER_CLIP),
                    "-y",
                    abs_out_16x9
                ]
                logger.info(f"Generating 16:9 clip {rank}: {start:.1f}s → {start+duration:.1f}s")
                res = subprocess.run(cmd_16x9, capture_output=True, text=True)
                
                if res.returncode != 0:
                    logger.error(f"16:9 clip {rank} generation failed: {res.stderr[-300:]}")
                else:
                    clip_data["file_path_landscape"] = output_rel_16x9

            except Exception as e:
                logger.error(f"Clip {clip_data.get('rank', idx+1)} failed: {e}")
                clip_data["file_path"] = ""
                clip_data["file_path_landscape"] = ""
                clip_data["error"] = str(e)
            return idx, clip_data

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_generate_one, idx, clip): idx
                for idx, clip in enumerate(clips_data)
            }

            for future in as_completed(futures):
                idx, clip_data = future.result()
                results[idx] = clip_data
                completed += 1

                if progress_callback:
                    progress_callback(completed, total)
                if on_clip_completed:
                    on_clip_completed(clip_data)

                rank = clip_data.get("rank", "?")
                has_error = "error" in clip_data
                status = "FAILED" if has_error else "OK"
                logger.info(f"Clip {rank} [{completed}/{total}] {status}")

        successful = sum(1 for r in results if r and r.get("file_path"))
        logger.info(f"Clip generation complete: {successful}/{total} successful")

        return [r for r in results if r is not None]

    # ── VIDEO INFO ─────────────────────────────────────────────────

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get video metadata."""
        abs_path = self.storage.get_absolute_path(video_path)
        cmd = [
            self.ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            abs_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {}

