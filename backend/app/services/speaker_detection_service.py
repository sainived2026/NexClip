"""
NexClip — FocusFrame Engine (v3.0)
Enterprise-Grade Speaker-Focused Cropping

┌─────────────────────────────────────────────────────────────────────┐
│  ROOT CAUSE FIX (v3.0):                                            │
│                                                                     │
│  Previous versions used YOLO "person" body center for cropping.     │
│  The body center includes torso/lap → crop lands on MICROPHONES.    │
│                                                                     │
│  v3.0 uses MediaPipe FACE DETECTION as the PRIMARY position source: │
│  - Face center_x → horizontal crop position (where to put the cam) │
│  - Face bounding box → headroom & framing calculations             │
│  - YOLO body detection → FALLBACK only when no faces found         │
│                                                                     │
│  SMOOTH CAMERA ANIMATION:                                           │
│  - Camera LOCKS during each speaker's turn                          │
│  - Camera SMOOTHLY GLIDES to next speaker on turn change (~0.4s)    │
│  - Bézier smoothstep (3t²−2t³) creates natural acceleration        │
└─────────────────────────────────────────────────────────────────────┘

Pipeline:
1. MediaPipe Face Detection → find all FACES → compute face centers
2. Per-face lip analysis → who is speaking (lip open/close ratio)
3. Speaker turn timeline → merge 0.5s windows into turns
4. Keyframes → locked positions + smooth transitions on speaker change
"""

import subprocess
import struct
import wave
import tempfile
import time
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from threading import Lock

import numpy as np
import cv2
from loguru import logger

from app.core.config import get_settings
from app.core.binaries import get_ffmpeg_path
from app.services.storage_service import get_storage

settings = get_settings()

# ── MediaPipe Lip Landmarks ────────────────────────────────────
UPPER_LIP_TOP = 13
LOWER_LIP_BOTTOM = 14
LIP_LEFT_CORNER = 61
LIP_RIGHT_CORNER = 291
NOSE_TIP = 1


# ── Data Classes ────────────────────────────────────────────────

@dataclass
class FaceTrack:
    """
    A tracked FACE across frames (using MediaPipe face mesh positions).
    
    KEY DIFFERENCE from v2: This tracks FACE center, not body center.
    Face center is the correct anchor for cropping because it ensures
    the camera focuses on the speaker's face, not their torso/mic area.
    """
    face_id: int
    # Face positions in SOURCE coordinates (already scaled up)
    face_centers_x: List[int] = field(default_factory=list)
    face_centers_y: List[int] = field(default_factory=list)
    face_widths: List[int] = field(default_factory=list)
    face_heights: List[int] = field(default_factory=list)
    lip_ratios: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    # Computed fixed position (median of all face detections)
    home_x: int = 0
    home_y: int = 0
    home_face_w: int = 0
    home_face_h: int = 0


@dataclass
class SpeakerKeyframe:
    """
    A keyframe for the cinematic camera director.
    
    Each keyframe represents a target camera position at a specific time.
    Between keyframes, the FFmpeg Bézier expression interpolates smoothly.
    """
    timestamp: float      # time in seconds (relative to clip start)
    center_x: int         # target crop center X (FACE center, not body)
    center_y: int         # target crop center Y (FACE center)
    face_top: int = 0     # face bbox top in source coords
    face_bottom: int = 0  # face bbox bottom in source coords
    face_width: int = 0   # face bbox width
    face_height: int = 0  # face bbox height
    end_time: float = 0.0 # when this segment ends


@dataclass
class CachedFaceTracks:
    """Cached face tracking data for a video range."""
    face_tracks: List[FaceTrack]
    video_start: float
    video_end: float
    src_width: int
    src_height: int
    created_at: float


@dataclass
class SpeakerDetectionResult:
    """Structured SCFS output for render-time diagnostics and persistence."""

    keyframes: List[SpeakerKeyframe] = field(default_factory=list)
    sfcs_version: str = "director_v4"
    sfcs_faces_detected: int = 0
    sfcs_frames_with_speaker: int = 0
    sfcs_fallback_frames: int = 0

    def to_clip_metadata(self) -> Dict[str, int | str]:
        return {
            "sfcs_version": self.sfcs_version,
            "sfcs_faces_detected": self.sfcs_faces_detected,
            "sfcs_frames_with_speaker": self.sfcs_frames_with_speaker,
            "sfcs_fallback_frames": self.sfcs_fallback_frames,
        }


class SpeakerDetectionService:
    """
    FocusFrame Engine v3.0: Face-First Speaker Detection.
    
    Uses MediaPipe Face Mesh as the PRIMARY detection method:
    - Face positions → crop centering (never body/torso)
    - Lip analysis per face → speaker identification
    - Smooth Bézier transitions between speaker turns
    """

    TRANSITION_DURATION = 0.4  # Seconds for smooth pan between speakers
    WINDOW_SIZE = 0.5          # Speaker analysis window in seconds
    MIN_TRACK_VISIBILITY_SCORE = 0.18
    SPEAKER_SWITCH_MARGIN = 1.18
    MIN_EVIDENCE_FRAMES = 24

    def __init__(self):
        self.storage = get_storage()
        self.ffmpeg_bin = get_ffmpeg_path()
        self._mp_face_mesh = None
        self._yolo_model = None
        self._vad = None
        self._track_cache: Dict[str, CachedFaceTracks] = {}
        self._cache_lock = Lock()
        self._detection_frame_width = settings.SPEAKER_DETECTION_FRAME_WIDTH

    # ── LAZY INIT ──────────────────────────────────────────────────

    def _init_mediapipe(self):
        if self._mp_face_mesh is not None:
            return
        try:
            import mediapipe as mp
            self._mp_face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=6,
                refine_landmarks=True,
                min_detection_confidence=0.4,
                min_tracking_confidence=0.4,
            )
            logger.info("MediaPipe FaceMesh initialized (face-first detection)")
        except ImportError:
            logger.error("mediapipe not installed! pip install mediapipe")
            raise

    def _init_yolo(self):
        if self._yolo_model is not None:
            return
        try:
            from ultralytics import YOLO
            self._yolo_model = YOLO("yolov8n.pt")
            logger.info("YOLOv8n initialized (fallback body detection)")
        except ImportError:
            logger.warning("ultralytics not installed, YOLO fallback disabled")

    def _init_vad(self):
        if self._vad is not None:
            return
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(2)
            logger.info("WebRTC VAD initialized")
        except ImportError:
            self._vad = None

    # ── PUBLIC API ─────────────────────────────────────────────────

    def precompute_face_tracks(
        self,
        video_path: str,
        clip_ranges: List[Tuple[float, float]],
        src_width: int,
        src_height: int,
    ) -> None:
        """Pre-compute face tracking for all clip ranges.
        
        PERF FIX: Only processes the actual clip ranges (with 2s margins),
        NOT the full span from min(start) to max(end). For 9 clips scattered
        across a 25-min video, this cuts processing time by ~60%.
        """
        if not settings.SPEAKER_DETECTION_ENABLED or not clip_ranges:
            return

        try:
            self._init_mediapipe()
        except Exception as e:
            logger.warning(f"Failed to init MediaPipe: {e}")
            return

        global_start = min(r[0] for r in clip_ranges)
        global_end = max(r[1] for r in clip_ranges)

        abs_path = self.storage.get_absolute_path(video_path)
        cache_key = video_path

        with self._cache_lock:
            if cache_key in self._track_cache:
                cached = self._track_cache[cache_key]
                if cached.video_start <= global_start and cached.video_end >= global_end:
                    logger.info("Face track cache HIT")
                    return

        t0 = time.perf_counter()
        sample_fps = settings.SPEAKER_DETECTION_SAMPLE_FPS

        # ── Merge overlapping ranges (with 2s margin) to minimize total scan ──
        sorted_ranges = sorted(clip_ranges, key=lambda r: r[0])
        merged_ranges = []
        for rng_start, rng_end in sorted_ranges:
            margin_start = max(0, rng_start - 2.0)
            margin_end = rng_end + 2.0
            if merged_ranges and margin_start <= merged_ranges[-1][1]:
                merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], margin_end))
            else:
                merged_ranges.append((margin_start, margin_end))

        total_scan = sum(e - s for s, e in merged_ranges)
        full_span = global_end - global_start
        logger.info(
            f"FocusFrame: scanning {total_scan:.0f}s across {len(merged_ranges)} merged ranges "
            f"(vs {full_span:.0f}s full span — {100*(1-total_scan/max(full_span,1)):.0f}% savings)"
        )

        # ── Process each merged range and combine face tracks ──
        all_face_tracks: List[FaceTrack] = []
        for rng_start, rng_end in merged_ranges:
            rng_duration = rng_end - rng_start
            tracks = self._extract_face_tracks(
                abs_path, rng_start, rng_duration, sample_fps, src_width, src_height
            )
            all_face_tracks.extend(tracks)

        # ── Merge duplicate face tracks across ranges using spatial proximity ──
        face_tracks = self._merge_cross_range_tracks(all_face_tracks, src_width, src_height)

        # Compute fixed "home" positions for each face
        for track in face_tracks:
            if track.face_centers_x:
                track.home_x = int(np.median(track.face_centers_x))
                track.home_y = int(np.median(track.face_centers_y))
                track.home_face_w = int(np.median(track.face_widths)) if track.face_widths else 100
                track.home_face_h = int(np.median(track.face_heights)) if track.face_heights else 100

        cached = CachedFaceTracks(
            face_tracks=face_tracks,
            video_start=global_start,
            video_end=global_end,
            src_width=src_width,
            src_height=src_height,
            created_at=time.perf_counter(),
        )

        with self._cache_lock:
            self._track_cache[cache_key] = cached

        elapsed = time.perf_counter() - t0
        logger.info(
            f"FocusFrame: {len(face_tracks)} faces tracked in {elapsed:.1f}s "
            f"[{global_start:.0f}s-{global_end:.0f}s, {len(merged_ranges)} segments]"
        )

    def _merge_cross_range_tracks(
        self,
        tracks: List[FaceTrack],
        src_width: int,
        src_height: int,
    ) -> List[FaceTrack]:
        """Merge face tracks from different time ranges that belong to the same person."""
        if len(tracks) <= 1:
            return tracks

        max_dist = 0.07 * np.sqrt(src_width**2 + src_height**2)
        merged: List[FaceTrack] = []

        for track in tracks:
            if not track.face_centers_x:
                continue
            cx = int(np.median(track.face_centers_x))
            cy = int(np.median(track.face_centers_y))

            # Try to merge with existing track
            best_idx = None
            best_dist = float("inf")
            for i, m in enumerate(merged):
                mx = int(np.median(m.face_centers_x))
                my = int(np.median(m.face_centers_y))
                dist = np.sqrt((cx - mx)**2 + (cy - my)**2)
                if dist < best_dist and dist < max_dist:
                    best_dist = dist
                    best_idx = i

            if best_idx is not None:
                m = merged[best_idx]
                m.face_centers_x.extend(track.face_centers_x)
                m.face_centers_y.extend(track.face_centers_y)
                m.face_widths.extend(track.face_widths)
                m.face_heights.extend(track.face_heights)
                m.lip_ratios.extend(track.lip_ratios)
                m.timestamps.extend(track.timestamps)
            else:
                merged.append(track)

        return merged

    def detect_active_speaker(
        self,
        video_path: str,
        start: float,
        duration: float,
        src_width: int,
        src_height: int,
    ) -> List[SpeakerKeyframe]:
        """
        Detect the active speaker and return smooth camera keyframes.
        
        FACE-FIRST approach:
        1. Find all faces using MediaPipe → get face centers
        2. Analyze lip movement per face → identify who is speaking
        3. Build speaker turn timeline → merge into turns
        4. Generate keyframes → locked positions + smooth transitions
        """
        return self.detect_active_speaker_with_metadata(
            video_path=video_path,
            start=start,
            duration=duration,
            src_width=src_width,
            src_height=src_height,
        ).keyframes

    def detect_active_speaker_with_metadata(
        self,
        video_path: str,
        start: float,
        duration: float,
        src_width: int,
        src_height: int,
    ) -> SpeakerDetectionResult:
        """Return speaker keyframes plus SCFS diagnostics for this clip."""
        if not settings.SPEAKER_DETECTION_ENABLED:
            return SpeakerDetectionResult()

        abs_path = self.storage.get_absolute_path(video_path)
        sample_fps = settings.SPEAKER_DETECTION_SAMPLE_FPS
        clip_end = start + duration
        result = SpeakerDetectionResult()

        # ── Get or compute face tracks ──
        clip_tracks = self._get_clip_face_tracks(
            video_path, abs_path, start, duration, sample_fps, src_width, src_height
        )

        if not clip_tracks:
            # FALLBACK 1: Try YOLO body detection if no faces found
            logger.info("No faces detected, trying YOLO body fallback...")
            clip_tracks = self._yolo_fallback(
                abs_path, start, duration, sample_fps, src_width, src_height
            )
        result.sfcs_faces_detected = len(clip_tracks)

        if not clip_tracks:
            result.keyframes = self._build_presence_fallback_keyframes(
                video_path, start, duration, src_width, src_height
            )
            result.sfcs_fallback_frames = self._estimate_sample_frame_count(duration, sample_fps)
            return result

        viable_tracks = self._filter_viable_tracks(clip_tracks, src_width, src_height)
        if len(viable_tracks) != len(clip_tracks):
            logger.info(
                f"Filtered SCFS tracks: {len(clip_tracks)} total -> {len(viable_tracks)} viable"
            )
        result.sfcs_faces_detected = len(viable_tracks)
        if not viable_tracks:
            result.keyframes = self._build_presence_fallback_keyframes(
                video_path, start, duration, src_width, src_height
            )
            result.sfcs_fallback_frames = self._estimate_sample_frame_count(duration, sample_fps)
            return result
        clip_tracks = viable_tracks

        # ── SINGLE FACE: Lock on them ──
        if len(clip_tracks) == 1:
            track = clip_tracks[0]
            home_x, home_y, face_w, face_h = self._build_track_snapshot(
                track,
                window_start=start,
                window_end=start + duration,
                grace_seconds=0.5,
            )
            face_top_val = max(0, home_y - face_h)
            
            logger.info(
                f"Single face — lock at ({home_x},{home_y}), "
                f"face {face_w}x{face_h}, face_top={face_top_val}, "
                f"src={src_width}x{src_height}"
            )
            result.keyframes = [SpeakerKeyframe(
                timestamp=start,
                center_x=home_x,
                center_y=home_y,
                face_top=face_top_val,
                face_bottom=min(src_height, home_y + face_h),
                face_width=face_w,
                face_height=face_h,
                end_time=start + duration,
            )]
            result.sfcs_frames_with_speaker = self._count_track_frames_in_window(
                [track], start, clip_end
            )
            return result

        # ── MULTIPLE FACES: Build speaker turns with smooth transitions ──
        logger.info(f"{len(clip_tracks)} faces — building speaker turn timeline")

        # Build speaker timeline from lip analysis
        speaker_timeline = self._build_speaker_timeline(
            clip_tracks, start, duration, sample_fps, src_width=src_width, src_height=src_height
        )

        # Convert to smooth camera keyframes
        keyframes = self._timeline_to_smooth_keyframes(
            speaker_timeline, clip_tracks, start, duration, src_width, src_height
        )
        result.keyframes = keyframes
        active_face_ids = {face_id for _, _, face_id in speaker_timeline}
        selected_tracks = [track for track in clip_tracks if track.face_id in active_face_ids]
        result.sfcs_frames_with_speaker = self._count_track_frames_in_window(
            selected_tracks or clip_tracks,
            start,
            clip_end,
        )

        logger.info(
            f"FocusFrame: {len(keyframes)} keyframes "
            f"({len(speaker_timeline)} speaker turns)"
        )
        return result

    def _borrow_nearest_face_from_cache(
        self,
        video_path: str,
        start: float,
        duration: float,
        src_width: int,
        src_height: int,
    ) -> Optional[SpeakerKeyframe]:
        """
        When no face/person is found in the current clip, search the global
        precomputed face track cache and borrow the position of the face
        whose timestamps are closest to this clip's time range.
        
        This prevents the camera from cropping to a random center where
        no person exists — instead, it locks on the nearest known person.
        """
        with self._cache_lock:
            cached = self._track_cache.get(video_path)
            if not cached or not cached.face_tracks:
                return None
        
        clip_mid = start + duration / 2  # Midpoint of this clip
        best_track = None
        best_distance = float("inf")
        
        for track in cached.face_tracks:
            if not track.timestamps:
                continue
            # Find the closest timestamp in this track to the clip midpoint
            closest_ts = min(track.timestamps, key=lambda t: abs(t - clip_mid))
            dist = abs(closest_ts - clip_mid)
            if dist < best_distance:
                best_distance = dist
                best_track = track
        
        if best_track is None or best_track.home_x <= 0:
            return None
        
        hx = best_track.home_x
        hy = best_track.home_y
        fw = best_track.home_face_w
        fh = best_track.home_face_h
        
        return SpeakerKeyframe(
            timestamp=start,
            center_x=hx,
            center_y=hy,
            face_top=max(0, hy - fh),
            face_bottom=min(src_height, hy + fh),
            face_width=fw,
            face_height=fh,
            end_time=start + duration,
        )

    @staticmethod
    def _ema_smooth(values: list, alpha: float = 0.3) -> list:
        """
        Apply Exponential Moving Average (EMA) smoothing to a list of values.
        
        α = 0.3 means each new value gets 30% weight, previous smoothed gets 70%.
        This filters out high-frequency jitter from per-frame face detection while
        preserving genuine position changes (e.g. speaker switch).
        """
        if not values or len(values) < 2:
            return list(values)
        smoothed = [values[0]]
        for v in values[1:]:
            smoothed.append(alpha * v + (1 - alpha) * smoothed[-1])
        return smoothed

    def clear_cache(self, video_path: str = None):
        with self._cache_lock:
            if video_path:
                self._track_cache.pop(video_path, None)
            else:
                self._track_cache.clear()
            logger.info(f"Cache cleared: {'all' if not video_path else video_path}")

    def _estimate_sample_frame_count(self, duration: float, sample_fps: int) -> int:
        if duration <= 0 or sample_fps <= 0:
            return 0
        return max(1, int(np.ceil(duration * sample_fps)))

    def _count_track_frames_in_window(
        self,
        tracks: List[FaceTrack],
        window_start: float,
        window_end: float,
    ) -> int:
        timestamps = {
            round(ts, 3)
            for track in tracks
            for ts in track.timestamps
            if window_start <= ts <= window_end
        }
        return len(timestamps)

    def _track_visibility_score(self, track: FaceTrack, src_width: int, src_height: int) -> float:
        """Estimate whether a face track is a usable on-screen person."""
        if src_width <= 0 or src_height <= 0 or track.home_face_h <= 0 or track.home_face_w <= 0:
            return 0.0

        half_w = max(1, track.home_face_w // 2)
        half_h = max(1, track.home_face_h // 2)
        face_left = track.home_x - half_w
        face_right = track.home_x + half_w
        face_top = track.home_y - half_h
        face_bottom = track.home_y + half_h

        raw_width = max(1, face_right - face_left)
        raw_height = max(1, face_bottom - face_top)
        visible_width = max(0, min(src_width, face_right) - max(0, face_left))
        visible_height = max(0, min(src_height, face_bottom) - max(0, face_top))
        horizontal_visible_ratio = visible_width / raw_width
        vertical_visible_ratio = visible_height / raw_height

        x_norm = track.home_x / max(src_width, 1)
        y_norm = track.home_y / max(src_height, 1)
        horizontal_score = max(0.0, 1.0 - abs(x_norm - 0.50) / 0.42)
        if 0.08 <= x_norm <= 0.92:
            horizontal_score = max(horizontal_score, 0.15)
        vertical_score = max(0.0, 1.0 - abs(y_norm - 0.42) / 0.30)
        if 0.10 <= y_norm <= 0.82:
            vertical_score = max(vertical_score, 0.15)

        return (
            horizontal_visible_ratio
            * vertical_visible_ratio
            * horizontal_score
            * vertical_score
        )

    def _track_sample_count(
        self,
        track: FaceTrack,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
        grace_seconds: float = 0.0,
    ) -> int:
        """Count detections for a track, optionally in a time-local window."""
        if window_start is None or window_end is None:
            return len(track.timestamps)

        expanded_start = window_start - max(0.0, grace_seconds)
        expanded_end = window_end + max(0.0, grace_seconds)
        return sum(1 for ts in track.timestamps if expanded_start <= ts <= expanded_end)

    def _filter_viable_tracks(self, tracks: List[FaceTrack], src_width: int, src_height: int) -> List[FaceTrack]:
        return [
            track for track in tracks
            if self._track_visibility_score(track, src_width, src_height) >= self.MIN_TRACK_VISIBILITY_SCORE
        ]

    def _pick_best_visible_track(
        self,
        tracks: List[FaceTrack],
        src_width: int,
        src_height: int,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
        grace_seconds: float = 0.0,
    ) -> Optional[FaceTrack]:
        candidates = []
        for track in tracks:
            presence_count = self._track_sample_count(
                track,
                window_start=window_start,
                window_end=window_end,
                grace_seconds=grace_seconds,
            )
            if window_start is not None and window_end is not None and presence_count == 0:
                continue

            visibility_score = self._track_visibility_score(track, src_width, src_height)
            presence_score = min(1.0, presence_count / 3.0) if presence_count else 0.0
            candidates.append(
                (
                    visibility_score * max(1, track.home_face_w * track.home_face_h) * (0.55 + 0.45 * presence_score),
                    presence_count,
                    track.home_face_w * track.home_face_h,
                    track,
                )
            )

        if not candidates:
            return None

        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return candidates[0][3]

    def _build_track_snapshot(
        self,
        track: FaceTrack,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
        grace_seconds: float = 0.35,
    ) -> Tuple[int, int, int, int]:
        """
        Build a stable, face-safe snapshot for a track.

        A track-wide median is smooth, but it can undershoot the true face size
        during a specific speaker turn when the person leans toward an edge.
        That lets the crop clip the visible face. We keep the center stable by
        using the local median, but size the face from a high percentile inside
        the local turn window.
        """
        indices: List[int] = []
        if window_start is not None and window_end is not None:
            expanded_start = window_start - max(0.0, grace_seconds)
            expanded_end = window_end + max(0.0, grace_seconds)
            indices = [
                i for i, ts in enumerate(track.timestamps)
                if expanded_start <= ts <= expanded_end
            ]

        if not indices:
            indices = list(range(len(track.timestamps)))

        if not indices:
            return (
                max(0, track.home_x),
                max(0, track.home_y),
                max(1, track.home_face_w),
                max(1, track.home_face_h),
            )

        centers_x = [track.face_centers_x[i] for i in indices if i < len(track.face_centers_x)]
        centers_y = [track.face_centers_y[i] for i in indices if i < len(track.face_centers_y)]
        widths = [track.face_widths[i] for i in indices if i < len(track.face_widths)]
        heights = [track.face_heights[i] for i in indices if i < len(track.face_heights)]

        if not centers_x:
            centers_x = [track.home_x]
        if not centers_y:
            centers_y = [track.home_y]
        if not widths:
            widths = [track.home_face_w or 1]
        if not heights:
            heights = [track.home_face_h or 1]

        smoothed_x = self._ema_smooth(centers_x, alpha=0.35)
        smoothed_y = self._ema_smooth(centers_y, alpha=0.35)
        center_x = int(np.median(smoothed_x))
        center_y = int(np.median(smoothed_y))
        face_w = int(max(track.home_face_w or 1, np.percentile(widths, 85)))
        face_h = int(max(track.home_face_h or 1, np.percentile(heights, 85)))

        return center_x, center_y, face_w, face_h

    def _build_presence_fallback_keyframes(
        self,
        video_path: str,
        start: float,
        duration: float,
        src_width: int,
        src_height: int,
    ) -> List[SpeakerKeyframe]:
        """Return the safest available fallback when the clip has no usable tracks."""
        borrowed_kf = self._borrow_nearest_face_from_cache(
            video_path, start, duration, src_width, src_height
        )
        if borrowed_kf:
            logger.info(
                f"No usable persons in clip {start:.1f}s-{start+duration:.1f}s - "
                f"borrowing nearest face at ({borrowed_kf.center_x},{borrowed_kf.center_y})"
            )
            return [borrowed_kf]

        logger.info(
            f"No usable persons near clip {start:.1f}s - using upper-third fallback"
        )
        return [SpeakerKeyframe(
            timestamp=start,
            center_x=src_width // 2,
            center_y=src_height // 3,
            face_top=0,
            face_bottom=src_height // 2,
            face_width=src_width // 4,
            face_height=src_height // 3,
            end_time=start + duration,
        )]

    # ── FACE TRACK EXTRACTION (PRIMARY) ────────────────────────────

    def _extract_face_tracks(
        self,
        video_path: str,
        start: float,
        duration: float,
        sample_fps: int,
        src_width: int,
        src_height: int,
    ) -> List[FaceTrack]:
        """
        Extract face tracks using MediaPipe Face Mesh.
        
        For each frame:
        1. Run MediaPipe face detection → get face landmarks
        2. Compute face center, width, height, lip ratio
        3. Scale from detection frame coords → source frame coords
        4. Group faces across frames using spatial proximity
        """
        try:
            self._init_mediapipe()
        except Exception:
            return []

        chunk_duration = 30.0  # Process 30s at a time to limit memory
        total_chunks = max(1, int(np.ceil(duration / chunk_duration)))
        
        frame_w = self._detection_frame_width
        frame_h = int(frame_w * src_height / src_width)
        
        # CRITICAL FIX: Correct scale factors from detection → source coordinates
        scale_x = src_width / frame_w
        scale_y = src_height / frame_h

        all_frame_faces = []  # List of (timestamp, [face_data, ...])

        for chunk_idx in range(total_chunks):
            chunk_start = start + chunk_idx * chunk_duration
            chunk_dur = min(chunk_duration, start + duration - chunk_start)
            if chunk_dur <= 0:
                break

            try:
                frames, timestamps = self._extract_frames_ffmpeg(
                    video_path, chunk_start, chunk_dur, sample_fps
                )
                if not frames:
                    continue

                for frame, ts in zip(frames, timestamps):
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = self._mp_face_mesh.process(rgb_frame)

                    frame_faces = []
                    if results.multi_face_landmarks:
                        fh, fw = frame.shape[:2]

                        for face_lm in results.multi_face_landmarks:
                            lm = face_lm.landmark

                            # ── Face center from nose tip (landmark 1) ──
                            nose_x_px = lm[NOSE_TIP].x * fw
                            nose_y_px = lm[NOSE_TIP].y * fh

                            # ── Face bounding box from all landmarks ──
                            xs = [l.x * fw for l in lm]
                            ys = [l.y * fh for l in lm]
                            face_left = min(xs)
                            face_right = max(xs)
                            face_top_px = min(ys)
                            face_bot_px = max(ys)
                            
                            face_w_px = face_right - face_left
                            face_h_px = face_bot_px - face_top_px
                            face_cx_px = (face_left + face_right) / 2
                            face_cy_px = (face_top_px + face_bot_px) / 2

                            # ── VALIDATION: Filter false positives ──
                            # Real faces have aspect ratio between 0.5 and 1.8
                            face_aspect = face_h_px / max(face_w_px, 1)
                            if face_aspect < 0.4 or face_aspect > 2.5:
                                continue

                            # Min face size: 3% of frame width (adaptive, not fixed pixel)
                            min_face_w = fw * 0.03
                            if face_w_px < min_face_w:
                                continue

                            # Face should be in the upper 80% of frame (not below desk)
                            if face_cy_px > fh * 0.85:
                                continue

                            # ── Lip analysis ──
                            vert = abs(lm[UPPER_LIP_TOP].y - lm[LOWER_LIP_BOTTOM].y) * fh
                            horiz = abs(lm[LIP_LEFT_CORNER].x - lm[LIP_RIGHT_CORNER].x) * fw
                            lip_ratio = vert / max(horiz, 1e-6)

                            # ── Scale to SOURCE coordinates ──
                            src_cx = int(face_cx_px * scale_x)
                            src_cy = int(face_cy_px * scale_y)
                            src_fw = int(face_w_px * scale_x)
                            src_fh = int(face_h_px * scale_y)
                            src_face_top = int(face_top_px * scale_y)

                            frame_faces.append({
                                "cx": src_cx,
                                "cy": src_cy,
                                "fw": src_fw,
                                "fh": src_fh,
                                "face_top": src_face_top,
                                "lip_ratio": lip_ratio,
                            })

                    all_frame_faces.append((ts, frame_faces))

                del frames

            except Exception as e:
                logger.warning(f"Face extraction chunk {chunk_idx+1} error: {e}")
                continue

        return self._build_face_tracks(all_frame_faces, src_width, src_height)

    def _build_face_tracks(
        self,
        frame_faces: List[Tuple[float, List[dict]]],
        src_width: int,
        src_height: int,
    ) -> List[FaceTrack]:
        """
        Build persistent face tracks by matching faces across frames
        using TIGHT spatial proximity of face centers.
        
        CRITICAL: max_dist must be SMALL enough that two different
        people's faces are NEVER merged into one track. For a 1920x1080
        podcast with two people, faces can be ~300px apart. We use 7%
        of diagonal (~154px) to keep them firmly separate.
        """
        tracks: List[FaceTrack] = []
        next_id = 0
        active_centers: Dict[int, Tuple[int, int]] = {}
        
        # TIGHT proximity: 7% of diagonal (was 15% — way too loose)
        # For 1920x1080: 0.07 * 2203 = 154px (safe for two podcast speakers)
        max_dist = 0.07 * np.sqrt(src_width**2 + src_height**2)

        for ts, faces in frame_faces:
            if not faces:
                continue

            used_tracks = set()

            for face in sorted(faces, key=lambda f: -f["fw"]):  # Largest face first
                cx, cy = face["cx"], face["cy"]
                best_tid = None
                best_dist = float("inf")

                for tid, (tcx, tcy) in active_centers.items():
                    if tid in used_tracks:
                        continue
                    dist = np.sqrt((cx - tcx)**2 + (cy - tcy)**2)
                    if dist < best_dist and dist < max_dist:
                        best_dist = dist
                        best_tid = tid

                if best_tid is not None:
                    track = tracks[best_tid]
                else:
                    track = FaceTrack(face_id=next_id)
                    tracks.append(track)
                    best_tid = next_id
                    next_id += 1

                track.face_centers_x.append(cx)
                track.face_centers_y.append(cy)
                track.face_widths.append(face["fw"])
                track.face_heights.append(face["fh"])
                track.lip_ratios.append(face["lip_ratio"])
                track.timestamps.append(ts)
                active_centers[best_tid] = (cx, cy)
                used_tracks.add(best_tid)

        # Compute home positions with EMA-stabilized centers
        for track in tracks:
            if track.face_centers_x:
                # EMA (Exponential Moving Average) smoothing to filter jitter
                # α=0.3 gives ~70% weight to previous smoothed value, 30% to new observation
                # This stabilizes per-frame face position fluctuations from MediaPipe
                smoothed_x = self._ema_smooth(track.face_centers_x, alpha=0.3)
                smoothed_y = self._ema_smooth(track.face_centers_y, alpha=0.3)
                track.home_x = int(np.median(smoothed_x))
                track.home_y = int(np.median(smoothed_y))
                track.home_face_w = int(np.median(track.face_widths))
                track.home_face_h = int(np.median(track.face_heights))

        # Filter: need at least 3 detections to be a real face,
        # but for NexClip, we want to filter out ultra-short false positives
        # (e.g. hands/objects detected as faces for < 1 second).
        # Require face track to be at least 10% of clip duration or cap at 10 frames (~2s).
        min_frames = min(max(3, int(len(frame_faces) * 0.1)), 10)
        tracks = [t for t in tracks if len(t.timestamps) >= min_frames]

        # ── TRACK SPLITTING: Detect and split merged tracks ──
        # If a single track has high X-variance, it likely contains
        # two different people's faces merged together.
        split_threshold = src_width * 0.08  # 8% of source width
        final_tracks = []
        for track in tracks:
            x_std = np.std(track.face_centers_x)
            if x_std > split_threshold and len(track.face_centers_x) >= 6:
                # This track likely contains two merged faces — split it
                logger.info(
                    f"Track {track.face_id} has high X-variance (std={x_std:.0f}px, "
                    f"threshold={split_threshold:.0f}px) — splitting into 2 tracks"
                )
                split_tracks = self._split_merged_track(track, next_id)
                final_tracks.extend(split_tracks)
                next_id += len(split_tracks)
            else:
                final_tracks.append(track)

        for t in final_tracks:
            logger.info(
                f"Face track {t.face_id}: home=({t.home_x},{t.home_y}), "
                f"face={t.home_face_w}x{t.home_face_h}, "
                f"detections={len(t.timestamps)}"
            )

        logger.info(f"Built {len(final_tracks)} face tracks from {len(frame_faces)} frames")
        return final_tracks

    def _split_merged_track(
        self, track: FaceTrack, start_id: int
    ) -> List[FaceTrack]:
        """
        Split a merged track into 2 separate tracks using K-means
        clustering on the X coordinates.
        """
        xs = np.array(track.face_centers_x)
        
        # Simple K-means with k=2
        # Use the min and max X as initial centroids
        c1 = np.min(xs)
        c2 = np.max(xs)
        
        for _ in range(10):  # 10 iterations is enough
            labels = (np.abs(xs - c1) > np.abs(xs - c2)).astype(int)
            if np.sum(labels == 0) > 0:
                c1 = np.mean(xs[labels == 0])
            if np.sum(labels == 1) > 0:
                c2 = np.mean(xs[labels == 1])

        # Build two separate tracks
        track_a = FaceTrack(face_id=start_id)
        track_b = FaceTrack(face_id=start_id + 1)

        labels = (np.abs(xs - c1) > np.abs(xs - c2)).astype(int)
        
        for i in range(len(track.timestamps)):
            target = track_a if labels[i] == 0 else track_b
            target.face_centers_x.append(track.face_centers_x[i])
            target.face_centers_y.append(track.face_centers_y[i])
            target.face_widths.append(track.face_widths[i])
            target.face_heights.append(track.face_heights[i])
            target.lip_ratios.append(track.lip_ratios[i])
            target.timestamps.append(track.timestamps[i])

        result = []
        for t in [track_a, track_b]:
            if len(t.timestamps) >= 3:
                t.home_x = int(np.median(t.face_centers_x))
                t.home_y = int(np.median(t.face_centers_y))
                t.home_face_w = int(np.median(t.face_widths))
                t.home_face_h = int(np.median(t.face_heights))
                result.append(t)
                logger.info(
                    f"  Split track {t.face_id}: home=({t.home_x},{t.home_y}), "
                    f"{len(t.timestamps)} detections"
                )

        return result if result else [track]

    # ── YOLO FALLBACK ──────────────────────────────────────────────

    def _yolo_fallback(
        self,
        video_path: str,
        start: float,
        duration: float,
        sample_fps: int,
        src_width: int,
        src_height: int,
    ) -> List[FaceTrack]:
        """
        Fallback: Use YOLO body detection when MediaPipe finds no faces.
        Convert body detections to FaceTrack format using the upper 25%
        of the body bbox as "face region".
        """
        try:
            self._init_yolo()
        except Exception:
            return []

        if self._yolo_model is None:
            return []

        frame_w = self._detection_frame_width
        frame_h = int(frame_w * src_height / src_width)
        scale_x = src_width / frame_w
        scale_y = src_height / frame_h

        try:
            frames, timestamps = self._extract_frames_ffmpeg(
                video_path, start, min(duration, 30.0), sample_fps
            )
        except Exception:
            return []

        if not frames:
            return []

        all_frame_faces = []

        for frame, ts in zip(frames, timestamps):
            results = self._yolo_model(frame, classes=[0], conf=0.4, verbose=False)
            
            frame_faces = []
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        
                        # Use UPPER 25% of body bbox as "face region"
                        body_h = y2 - y1
                        face_top = y1
                        face_bot = y1 + body_h * 0.25
                        face_cx = (x1 + x2) / 2
                        face_cy = (face_top + face_bot) / 2

                        src_cx = int(face_cx * scale_x)
                        src_cy = int(face_cy * scale_y)
                        src_fw = int((x2 - x1) * 0.5 * scale_x)
                        src_fh = int(body_h * 0.25 * scale_y)

                        frame_faces.append({
                            "cx": src_cx,
                            "cy": src_cy,
                            "fw": src_fw,
                            "fh": src_fh,
                            "face_top": int(face_top * scale_y),
                            "lip_ratio": 0.0,
                        })

            all_frame_faces.append((ts, frame_faces))

        del frames
        return self._build_face_tracks(all_frame_faces, src_width, src_height)

    # ── SPEAKER TIMELINE ───────────────────────────────────────────

    def _build_speaker_timeline(
        self,
        tracks: List[FaceTrack],
        start: float,
        duration: float,
        sample_fps: int,
        src_width: int = 1920,
        src_height: int = 1080,
    ) -> List[Tuple[float, float, int]]:
        """
        Build speaker turn timeline: [(turn_start, turn_end, face_id), ...]
        
        Uses lip movement analysis per face to identify the active speaker
        in each time window. Lip ratio variance = speaking confidence.
        """
        # Get VAD signal
        # (skipping for now since lip analysis is sufficient with face-first)

        window_size = self.WINDOW_SIZE
        n_windows = max(1, int(duration / window_size))
        
        current_speaker_id = None
        last_known_speaker_id = None  # Face-presence guarantee: hold last speaker when no face found
        best_visible_track = self._pick_best_visible_track(tracks, src_width, src_height)
        total_face_area = max(
            1,
            sum(max(1, t.home_face_w * t.home_face_h) for t in tracks),
        )
        
        window_speakers = []
        for w in range(n_windows):
            w_start = start + w * window_size
            w_end = min(w_start + window_size, start + duration)
            window_visible_track = self._pick_best_visible_track(
                tracks,
                src_width,
                src_height,
                window_start=w_start,
                window_end=w_end,
                grace_seconds=window_size,
            )
            
            best_track = None
            best_score = -1.0
            current_speaker_score = None
            track_scores: Dict[int, float] = {}
            
            for track in tracks:
                visibility_score = self._track_visibility_score(track, src_width, src_height)
                if visibility_score < self.MIN_TRACK_VISIBILITY_SCORE:
                    continue

                # Get lip data within this window
                window_lips = []
                for i, ts in enumerate(track.timestamps):
                    if w_start <= ts <= w_end and i < len(track.lip_ratios):
                        window_lips.append(track.lip_ratios[i])
                
                if not window_lips:
                    continue
                
                # Score: lip movement variance + mean openness
                # Higher variance = mouth opening and closing = speaking
                lip_var = np.var(window_lips) if len(window_lips) > 1 else 0
                lip_mean = np.mean(window_lips)
                
                # Variance is the strongest signal (mouth moving up and down)
                score = lip_var * 1000 + lip_mean * 3
                
                # Bonus for larger faces (closer = more likely main speaker)
                if track.home_face_w > 0:
                    face_area_ratio = (track.home_face_w * track.home_face_h) / total_face_area
                    score += face_area_ratio * 2
                    evidence_score = min(1.0, len(window_lips) / 3.0)
                    score *= (0.55 + 0.45 * evidence_score)
                    score *= (0.40 + 0.60 * visibility_score)
                
                # ── INERTIA: Bias toward current speaker ──
                if current_speaker_id is not None and track.face_id == current_speaker_id:
                    current_speaker_score = score
                track_scores[track.face_id] = score

                if score > best_score:
                    best_score = score
                    best_track = track

            if (
                current_speaker_id is None
                and best_track is not None
                and window_visible_track is not None
                and best_track.face_id != window_visible_track.face_id
            ):
                visible_track_score = track_scores.get(window_visible_track.face_id)
                if (
                    visible_track_score is not None
                    and best_score < visible_track_score * self.SPEAKER_SWITCH_MARGIN
                ):
                    best_track = window_visible_track

            if (
                current_speaker_id is not None
                and best_track is not None
                and best_track.face_id != current_speaker_id
                and current_speaker_score is not None
                and best_score < current_speaker_score * self.SPEAKER_SWITCH_MARGIN
            ):
                best_track = next(
                    (track for track in tracks if track.face_id == current_speaker_id),
                    best_track,
                )

            if best_track:
                current_speaker_id = best_track.face_id
                last_known_speaker_id = best_track.face_id
                window_speakers.append((w_start, w_end, best_track.face_id))
            elif window_visible_track is not None:
                current_speaker_id = window_visible_track.face_id
                last_known_speaker_id = window_visible_track.face_id
                window_speakers.append((w_start, w_end, window_visible_track.face_id))
            elif last_known_speaker_id is not None:
                # Face-presence guarantee: hold the last known speaker
                # so the crop NEVER jumps to empty space
                window_speakers.append((w_start, w_end, last_known_speaker_id))
            elif best_visible_track is not None:
                last_known_speaker_id = best_visible_track.face_id
                window_speakers.append((w_start, w_end, best_visible_track.face_id))

        if not window_speakers:
            fallback_track = self._pick_best_visible_track(tracks, src_width, src_height)
            return [(start, start + duration, fallback_track.face_id if fallback_track else 0)]

        # ── Merge consecutive windows of the same speaker ──
        merged = []
        cur_start, cur_end, cur_speaker = window_speakers[0]
        
        for w_start, w_end, speaker_id in window_speakers[1:]:
            if speaker_id == cur_speaker:
                cur_end = w_end
            else:
                merged.append((cur_start, cur_end, cur_speaker))
                cur_start = w_start
                cur_end = w_end
                cur_speaker = speaker_id
        merged.append((cur_start, cur_end, cur_speaker))

        # Filter out very short turns (< 2.5s) — absorb into previous
        # This prevents sub-second camera switches that look jarring
        filtered = []
        for turn_start, turn_end, speaker_id in merged:
            if turn_end - turn_start < 2.5 and filtered:
                prev = filtered[-1]
                filtered[-1] = (prev[0], turn_end, prev[2])
            else:
                filtered.append((turn_start, turn_end, speaker_id))

        logger.info(f"Speaker timeline: {len(filtered)} turns from {len(window_speakers)} windows")
        return filtered

    def _timeline_to_smooth_keyframes(
        self,
        timeline: List[Tuple[float, float, int]],
        tracks: List[FaceTrack],
        clip_start: float,
        clip_duration: float,
        src_width: int,
        src_height: int,
    ) -> List[SpeakerKeyframe]:
        """
        Convert speaker timeline → smooth camera keyframes.
        
        For each turn:
        1. START keyframe at turn_start (face center position)
        2. END keyframe at turn_end - 0.1s (same position → camera locked)
        
        Between turns, the Bézier expression smoothly interpolates
        from the previous position to the new one → smooth camera pan.
        """
        face_homes: Dict[int, Tuple[int, int, int, int]] = {}
        for track in tracks:
            face_homes[track.face_id] = self._build_track_snapshot(
                track,
                window_start=clip_start,
                window_end=clip_start + clip_duration,
                grace_seconds=self.WINDOW_SIZE,
            )

        keyframes = []

        for i, (turn_start, turn_end, face_id) in enumerate(timeline):
            home = face_homes.get(face_id)
            if not home:
                continue
            
            track = next((candidate for candidate in tracks if candidate.face_id == face_id), None)
            if track is not None:
                hx, hy, fw, fh = self._build_track_snapshot(
                    track,
                    window_start=turn_start,
                    window_end=turn_end,
                    grace_seconds=self.WINDOW_SIZE,
                )
            else:
                hx, hy, fw, fh = home
            face_top = max(0, hy - fh)
            face_bottom = min(src_height, hy + fh)

            # Start of turn keyframe
            if i == 0:
                # First turn: lock at clip_start
                keyframes.append(SpeakerKeyframe(
                    timestamp=clip_start,
                    center_x=hx, center_y=hy,
                    face_top=face_top, face_bottom=face_bottom,
                    face_width=fw, face_height=fh,
                    end_time=turn_end,
                ))
            else:
                # Transition from previous speaker: insert keyframe at turn_start
                keyframes.append(SpeakerKeyframe(
                    timestamp=turn_start,
                    center_x=hx, center_y=hy,
                    face_top=face_top, face_bottom=face_bottom,
                    face_width=fw, face_height=fh,
                    end_time=turn_end,
                ))

            # End of turn keyframe (same position → camera stays still during turn)
            if turn_end > turn_start + 0.5:
                keyframes.append(SpeakerKeyframe(
                    timestamp=turn_end - 0.1,
                    center_x=hx, center_y=hy,
                    face_top=face_top, face_bottom=face_bottom,
                    face_width=fw, face_height=fh,
                    end_time=turn_end,
                ))

        if not keyframes:
            # Fallback: use the LARGEST face (NOT the center of frame!)
            if tracks:
                largest = self._pick_best_visible_track(tracks, src_width, src_height) or max(
                    tracks, key=lambda t: t.home_face_w * t.home_face_h
                )
                hx, hy = largest.home_x, largest.home_y
                fw, fh = largest.home_face_w, largest.home_face_h
                logger.warning(f"Keyframe fallback: using visible face at ({hx},{hy})")
            else:
                hx, hy = src_width // 2, src_height // 3
                fw, fh = 80, 100
                logger.warning(f"Keyframe fallback: NO faces, using center ({hx},{hy})")
            keyframes.append(SpeakerKeyframe(
                timestamp=clip_start,
                center_x=hx, center_y=hy,
                face_top=max(0, hy - fh), face_bottom=min(src_height, hy + fh),
                face_width=fw, face_height=fh,
                end_time=clip_start + clip_duration,
            ))

        # ── Micro-jitter deadzone: clamp adjacent keyframes that are very close ──
        # If position delta between consecutive keyframes is < 2% of source width,
        # lock them together. This eliminates sub-pixel camera drift that looks like shaking.
        jitter_threshold_x = max(20, int(src_width * 0.02))
        jitter_threshold_y = max(15, int(src_height * 0.02))
        for i in range(1, len(keyframes)):
            prev = keyframes[i - 1]
            curr = keyframes[i]
            if abs(curr.center_x - prev.center_x) < jitter_threshold_x:
                curr.center_x = prev.center_x
            if abs(curr.center_y - prev.center_y) < jitter_threshold_y:
                curr.center_y = prev.center_y

        # Log all keyframe positions for debugging
        for kf in keyframes:
            logger.debug(
                f"  KF t={kf.timestamp:.1f}: center=({kf.center_x},{kf.center_y}), "
                f"face={kf.face_width}x{kf.face_height}"
            )

        return keyframes

    # ── CACHE ──────────────────────────────────────────────────────

    def _get_clip_face_tracks(
        self,
        video_path: str,
        abs_path: str,
        start: float,
        duration: float,
        sample_fps: int,
        src_width: int,
        src_height: int,
    ) -> List[FaceTrack]:
        """Get face tracks for a clip, using cache if available."""
        with self._cache_lock:
            cached = self._track_cache.get(video_path)
            if cached and cached.video_start <= start and cached.video_end >= start + duration:
                clip_tracks = self._filter_tracks_for_clip(
                    cached.face_tracks, start, duration
                )
                if clip_tracks:
                    return clip_tracks

        # Not cached → extract fresh
        return self._extract_face_tracks(
            abs_path, start, duration, sample_fps, src_width, src_height
        )

    def _filter_tracks_for_clip(
        self,
        tracks: List[FaceTrack],
        clip_start: float,
        clip_duration: float,
    ) -> List[FaceTrack]:
        """Filter face tracks to a specific clip time range."""
        clip_end = clip_start + clip_duration
        result = []
        min_detections = 2 if clip_duration <= 1.5 else 3

        for track in tracks:
            ct = FaceTrack(face_id=track.face_id)
            for i, ts in enumerate(track.timestamps):
                if clip_start <= ts <= clip_end:
                    ct.face_centers_x.append(track.face_centers_x[i])
                    ct.face_centers_y.append(track.face_centers_y[i])
                    ct.face_widths.append(track.face_widths[i] if i < len(track.face_widths) else 80)
                    ct.face_heights.append(track.face_heights[i] if i < len(track.face_heights) else 100)
                    ct.lip_ratios.append(track.lip_ratios[i] if i < len(track.lip_ratios) else 0.0)
                    ct.timestamps.append(ts)

            if len(ct.timestamps) >= min_detections:
                ct.home_x = int(np.median(ct.face_centers_x))
                ct.home_y = int(np.median(ct.face_centers_y))
                ct.home_face_w = int(np.median(ct.face_widths))
                ct.home_face_h = int(np.median(ct.face_heights))
                result.append(ct)

        return result

    # ── FRAME EXTRACTION ───────────────────────────────────────────

    def _extract_frames_ffmpeg(
        self,
        video_path: str,
        start: float,
        duration: float,
        sample_fps: int,
    ) -> Tuple[List[np.ndarray], List[float]]:
        """Extract frames from video using FFmpeg pipe."""
        target_w = self._detection_frame_width
        cmd = [
            self.ffmpeg_bin,
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
            "-vf", f"fps={sample_fps},scale={target_w}:-2",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-v", "error",
            "-"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=180)
            if result.returncode != 0 or len(result.stdout) == 0:
                return [], []

            raw = result.stdout
            bytes_per_row = target_w * 3
            total_rows = len(raw) // bytes_per_row
            if total_rows == 0:
                return [], []

            expected_frames = max(1, int(duration * sample_fps))
            frame_h = total_rows // expected_frames
            if frame_h <= 0:
                frame_h = total_rows

            # Ensure frame_h is even (FFmpeg scale=-2 guarantees even height)
            frame_h = frame_h & ~1 if frame_h > 1 else frame_h

            frame_size = target_w * frame_h * 3
            n_frames = len(raw) // frame_size

            frames, timestamps = [], []
            for i in range(n_frames):
                offset = i * frame_size
                fb = raw[offset:offset + frame_size]
                if len(fb) < frame_size:
                    break
                frame = np.frombuffer(fb, dtype=np.uint8).reshape((frame_h, target_w, 3))
                frames.append(frame)
                timestamps.append(start + i / sample_fps)

            return frames, timestamps

        except Exception as e:
            logger.warning(f"Frame extraction error: {e}")
            return [], []


# ── Singleton ──
_speaker_service: Optional[SpeakerDetectionService] = None


def get_speaker_detection_service() -> SpeakerDetectionService:
    global _speaker_service
    if _speaker_service is None:
        _speaker_service = SpeakerDetectionService()
    return _speaker_service
