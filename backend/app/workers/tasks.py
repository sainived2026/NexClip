"""
NexClip — Celery Task Definitions
The main video processing pipeline runs as a background task.

Production Architecture:
- Pipeline stages run sequentially: Download → Transcribe → AI Analysis → Clip Generation
- Speaker detection is PRE-COMPUTED once for all clips before generation begins
- Clip generation runs in PARALLEL via ThreadPoolExecutor (FFmpegService handles this)
- Granular progress updates at every stage for real-time frontend tracking
"""

import json
import os
import time
import traceback
import re
from datetime import datetime, timezone
from loguru import logger

from app.workers.celery_app import celery_app
from app.db.database import SessionLocal
from app.db.models import Project, Video, Transcript, Clip, ProjectStatus
from app.services.storage_service import get_storage
from app.services.transcription_service import TranscriptionService
from app.services.ai_scoring_service import AIClipScoringService
from app.services.ffmpeg_service import FFmpegService
from app.services.clip_dedup import dedupe_clip_dicts
from app.services.download_service import DownloadService
from app.services.speaker_detection_service import get_speaker_detection_service


class CheckpointManager:
    """Manages pipeline checkpoints to resume from failure points."""
    def __init__(self, storage, project_folder: str):
        self.storage = storage
        self.project_folder = project_folder
        self.checkpoint_path = storage.get_absolute_path(os.path.join(project_folder, "_checkpoint.json"))
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")
        return {"completed_stages": [], "generated_clips": [], "clip_candidates": [], "segments": []}

    def save_stage(self, stage_name: str, extra_data: dict = None):
        """Mark a stage as completed and save extra data."""
        if stage_name not in self.data["completed_stages"]:
            self.data["completed_stages"].append(stage_name)
        if extra_data:
            self.data.update(extra_data)
        self._write()

    def is_completed(self, stage_name: str) -> bool:
        return stage_name in self.data.get("completed_stages", [])

    def add_generated_clip(self, clip_data: dict):
        """Track a successfully generated clip."""
        if "generated_clips" not in self.data:
            self.data["generated_clips"] = []
        # Prevent duplicates based on rank
        ranks = [c.get("rank") for c in self.data["generated_clips"]]
        if clip_data.get("rank") not in ranks:
            self.data["generated_clips"].append(clip_data)
        self._write()

    def _write(self):
        try:
            os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
            with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to write checkpoint: {e}")


class ProjectTaskLock:
    """Best-effort per-project execution lock for Celery video tasks."""

    def __init__(self, lock_path: str, owner_id: str, stale_seconds: int = 6 * 60 * 60):
        self.lock_path = lock_path
        self.owner_id = owner_id
        self.stale_seconds = stale_seconds
        self.acquired = False

    def acquire(self) -> bool:
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        self._clear_if_stale()

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(self.lock_path, flags)
        except FileExistsError:
            return False

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "owner_id": self.owner_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "pid": os.getpid(),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        self.acquired = True
        return True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except Exception as exc:
            logger.warning(f"Failed to release project task lock {self.lock_path}: {exc}")
        finally:
            self.acquired = False

    def _clear_if_stale(self) -> None:
        if not os.path.exists(self.lock_path):
            return
        try:
            with open(self.lock_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            pid = payload.get("pid")
            if pid and not self._pid_is_running(int(pid)):
                os.remove(self.lock_path)
                return
            created_at = payload.get("created_at", "")
            if created_at:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - created).total_seconds()
                if age_seconds > self.stale_seconds:
                    os.remove(self.lock_path)
        except Exception:
            # If the lock is unreadable/corrupt, prefer recovery over permanent blockage.
            try:
                os.remove(self.lock_path)
            except Exception:
                pass

    @staticmethod
    def _pid_is_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True


def _update_project(db, project_id: str, **kwargs):
    """Helper to update project status in DB."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        for key, val in kwargs.items():
            setattr(project, key, val)
        db.commit()


def _build_completion_status_message(
    clip_count: int,
    total_time: float,
    transcribe_time: float | None,
    ai_time: float | None,
    speaker_time: float | None,
    clip_gen_time: float | None,
) -> str:
    """Build a stable completion message even when some stages were restored from cache/checkpoints."""
    return (
        f"Complete! {clip_count} clips generated in {total_time:.0f}s "
        f"(transcribe={(transcribe_time or 0):.0f}s, AI={(ai_time or 0):.0f}s, "
        f"speaker={(speaker_time or 0):.0f}s, render={(clip_gen_time or 0):.0f}s)"
    )


def _build_completion_project_update(
    clip_count: int,
    total_time: float,
    transcribe_time: float | None,
    ai_time: float | None,
    speaker_time: float | None,
    clip_gen_time: float | None,
) -> dict:
    """Build the final project update payload for a successful pipeline run."""
    return {
        "status": ProjectStatus.COMPLETED,
        "progress": 100,
        "error_message": None,
        "status_message": _build_completion_status_message(
            clip_count=clip_count,
            total_time=total_time,
            transcribe_time=transcribe_time,
            ai_time=ai_time,
            speaker_time=speaker_time,
            clip_gen_time=clip_gen_time,
        ),
    }


def _normalize_pipeline_error_message(error: Exception | str) -> str:
    """
    Convert low-level pipeline errors into user-actionable project messages.
    """
    text = str(error or "").strip()
    lowered = text.lower()

    if "confirm you're not a bot" in lowered or "[youtube]" in lowered and "cookies" in lowered:
        return (
            "YouTube blocked the server download. Export fresh authenticated cookies "
            "to backend/cookies.txt, restart the backend and Celery worker, then retry."
        )

    return text[:1000]


def _generate_video_summary(segments, project, project_folder, storage):
    """Generate a brief summary of the video content from its transcription."""
    from app.services.llm_service import LLMService

    # Build transcript text from segments
    transcript_text = " ".join(seg.get("text", "") for seg in segments[:100])  # Cap at 100 segments
    if len(transcript_text) > 5000:
        transcript_text = transcript_text[:5000] + "..."

    llm = LLMService()
    summary = llm.generate(
        system_prompt=(
            "You are a video content summarizer. Given a video transcription, "
            "generate a brief, concise summary (3-5 sentences) of what the video is about. "
            "Focus on the main topic, key points, and the overall tone. "
            "Return ONLY the summary text, nothing else."
        ),
        user_message=(
            f"Video title: {project.title}\n\n"
            f"Transcription:\n{transcript_text}"
        ),
    )

    # Save summary
    summary_dir = storage.get_absolute_path(f"{project_folder}/summary")
    os.makedirs(summary_dir, exist_ok=True)
    summary_data = {
        "project_id": project.id,
        "title": project.title,
        "summary": summary.strip(),
        "word_count": len(transcript_text.split()),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    summary_path = os.path.join(summary_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Video summary saved to {summary_path}")


@celery_app.task(bind=True, name="nexclip.process_video", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_video_task(self, project_id: str):
    """
    Main video processing pipeline:
    1. Download (if URL) / Validate upload
    2. Extract audio
    3. Transcribe with Whisper
    4. AI clip selection
    5. Pre-compute speaker detection (ONCE for all clips)
    6. FFmpeg parallel clip generation
    7. Save results to DB
    """
    db = SessionLocal()
    storage = get_storage()
    pipeline_start = time.perf_counter()
    transcribe_time = 0.0
    ai_time = 0.0
    speaker_time = 0.0
    clip_gen_time = 0.0
    speaker_service = None
    project_lock = None

    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"Project {project_id} not found")
            return

        video = project.video
        if not video:
            _update_project(db, project_id, status=ProjectStatus.FAILED, error_message="No video found")
            return

        logger.info(f"Starting pipeline for project {project_id}")
        _update_project(db, project_id, error_message=None)
        
        safe_title = re.sub(r'[\\/*?:"<>| ]', '_', project.title)
        project_folder = f"{safe_title}_{project.id[:8]}"
        lock_path = storage.get_absolute_path(os.path.join(project_folder, "_pipeline.lock"))
        project_lock = ProjectTaskLock(lock_path=lock_path, owner_id=getattr(self.request, "id", project_id))
        if not project_lock.acquire():
            logger.warning(f"Skipping duplicate pipeline task for project {project_id}: another worker owns {lock_path}")
            return
        cm = CheckpointManager(storage, project_folder)

        # ─── Step 0: Download if URL ────────────────────────────
        if video.source_url and not video.file_path:
            _update_project(
                db, project_id,
                status=ProjectStatus.UPLOADED,
                progress=5,
                status_message="Downloading video from URL...",
            )
            dl_service = DownloadService()
            dl_result = dl_service.download_video(video.source_url, project_folder)
            video.file_path = dl_result["file_path"]
            video.original_filename = dl_result["filename"]
            video.file_size_bytes = dl_result["file_size"]
            db.commit()

        # ─── Step 1: Extract audio ──────────────────────────────
        _update_project(
            db, project_id,
            status=ProjectStatus.TRANSCRIBING,
            progress=15,
            status_message="Extracting audio from video...",
        )
        transcription_service = TranscriptionService()
        audio_path = f"{project_folder}/audio/audio.wav"
        transcription_service.extract_audio(video.file_path, audio_path)

        # Get duration
        try:
            video.duration_seconds = transcription_service.get_video_duration(video.file_path)
            db.commit()
        except Exception as dur_err:
            logger.warning(f"Could not get video duration: {dur_err}")

        # ─── Step 2: Transcribe (or load cached) ────────────────

        existing_transcript = db.query(Transcript).filter(Transcript.project_id == project_id).first()
        
        if existing_transcript:
            logger.info(f"✅ Found existing transcript ({existing_transcript.file_path}), skipping STT!")
            _update_project(
                db, project_id,
                progress=48,
                status_message="Loaded existing transcript. Skipping STT...",
            )
            # Load segments from disk
            abs_transcript_path = storage.get_absolute_path(existing_transcript.file_path)
            try:
                with open(abs_transcript_path, 'r', encoding='utf-8') as f:
                    segments = json.load(f)
                transcription_service = TranscriptionService() # Need this for later references if any
            except Exception as e:
                logger.error(f"Failed to load cached transcript, falling back to STT: {e}")
                existing_transcript = None
                
        if not existing_transcript:
            _update_project(
                db, project_id,
                progress=30,
                status_message="Transcribing audio with AI speech-to-text...",
            )

            # Progress callback — updates DB in real-time so frontend shows progress
            def _on_stt_progress(percent: int, message: str):
                logger.info(f"STT pipeline progress: {percent}% — {message}")
                _update_project(db, project_id, progress=percent, status_message=message)

            t0 = time.perf_counter()
            segments = transcription_service.transcribe(audio_path, on_progress=_on_stt_progress)
            transcribe_time = time.perf_counter() - t0
            logger.info(f"Transcription completed in {transcribe_time:.1f}s ({len(segments)} segments)")



            # Save transcript
            transcript_path = transcription_service.save_transcript(segments, project_folder)
            transcript = Transcript(
                file_path=transcript_path,
                word_count=sum(len(s["text"].split()) for s in segments),
                project_id=project_id,
            )
            db.add(transcript)
            db.commit()

        # ─── Step 3: AI Clip Analysis ──────────────────────────
        if cm.is_completed("ai_analysis"):
            clip_candidates = cm.data.get("clip_candidates", [])
            _update_project(
                db, project_id,
                progress=60,
                status_message=f"Restored {len(clip_candidates)} high-potential clips from checkpoint...",
            )
            logger.info("Skipped AI analysis (loaded from checkpoint)")
        else:
            _update_project(
                db, project_id,
                status=ProjectStatus.ANALYZING,
                progress=50,
                status_message="AI is analyzing transcript for viral segments...",
            )
            t0 = time.perf_counter()
            scoring_service = AIClipScoringService()
            clip_candidates = scoring_service.analyze_transcript(
                transcript=segments,
                video_title=project.title,
                clip_count=project.clip_count,
                client_id=project.client_id,
            )
            ai_time = time.perf_counter() - t0
            logger.info(f"AI analysis completed in {ai_time:.1f}s ({len(clip_candidates)} clips)")
    
            _update_project(
                db, project_id,
                progress=60,
                status_message=f"Found {len(clip_candidates)} high-potential clips. Preparing generation...",
            )
            cm.save_stage("ai_analysis", {"clip_candidates": clip_candidates})

        # ─── Step 4: Pre-compute Speaker Detection (ONCE) ──────
        t0 = time.perf_counter()
        ffmpeg_service = FFmpegService()
        src_width, src_height = ffmpeg_service._get_video_dimensions(video.file_path)
        if cm.is_completed("speaker_detection"):
            logger.info("Skipped speaker detection (already completed in checkpoint)")
        else:
            _update_project(
                db, project_id,
                progress=65,
                status_message="Detecting speakers across all clip ranges...",
            )
    
            # Build clip ranges for precompute
            clip_ranges = [
                (float(c["start"]), float(c["end"]))
                for c in clip_candidates
                if "start" in c and "end" in c
            ]
    
            # Pre-compute speaker detection for ALL clips in one pass
            speaker_service = get_speaker_detection_service()
            speaker_service.precompute_face_tracks(
                video.file_path, clip_ranges, src_width, src_height
            )
            speaker_time = time.perf_counter() - t0
            logger.info(f"Speaker pre-detection completed in {speaker_time:.1f}s for {len(clip_ranges)} clip ranges")
            cm.save_stage("speaker_detection")

        # ─── Step 5: FFmpeg Parallel Clip Generation ─────────────
        generated_clips = dedupe_clip_dicts(cm.data.get("generated_clips", []))
        completed_ranks = [c.get("rank") for c in generated_clips]
        clips_to_generate = [c for c in clip_candidates if c.get("rank") not in completed_ranks]
        if not clips_to_generate:
            logger.info("All clips already generated from checkpoint.")
        else:
            _update_project(
                db, project_id,
                status=ProjectStatus.GENERATING_CLIPS,
                progress=70,
                status_message=f"Generating {len(clips_to_generate)} clips in parallel...",
            )
    
            def _progress_callback(completed_batch: int, total_batch: int):
                """Update progress during parallel clip generation."""
                total = len(clip_candidates)
                completed_total = len(completed_ranks) + completed_batch
                pct = 70 + int((completed_total / total) * 25)  # 70-95% range
                _update_project(
                    db, project_id,
                    progress=pct,
                    status_message=f"Rendering clip {completed_total}/{total}...",
                )
                
            def _clip_completed_callback(clip_data):
                cm.add_generated_clip(clip_data)
    
            t0 = time.perf_counter()
            new_generated_clips = ffmpeg_service.generate_all_clips(
                video_path=video.file_path,
                clips_data=clips_to_generate,
                project_folder=project_folder,
                progress_callback=_progress_callback,
                on_clip_completed=_clip_completed_callback,
            )
            clip_gen_time = time.perf_counter() - t0
            logger.info(f"Clip generation completed in {clip_gen_time:.1f}s")
            generated_clips = dedupe_clip_dicts([*generated_clips, *new_generated_clips])

        generated_clips = dedupe_clip_dicts(generated_clips)

        # ─── Step 6: Save clips to DB ──────────────────────────
        # Clear existing to avoid duplicates on resume
        db.query(Clip).filter(Clip.project_id == project_id).delete()
        db.commit()
        
        for i, clip_data in enumerate((sorted(generated_clips, key=lambda c: c.get("rank", 999)))):
            # Extract word-level timestamps from transcript segments for caption engine
            clip_start = clip_data["start"]
            clip_end = clip_data["end"]
            word_timestamps_list = []
            for seg in segments:
                seg_words = seg.get("words", [])
                for w in seg_words:
                    w_start = w.get("start", 0)
                    w_end = w.get("end", 0)
                    if w_start >= clip_start and w_end <= clip_end:
                        word_timestamps_list.append({
                            "word": w.get("word", w.get("text", "")),
                            "start": w_start - clip_start,  # Relative to clip start
                            "end": w_end - clip_start,
                        })
            # Fallback: if no word-level timestamps, create from segment text
            if not word_timestamps_list:
                for seg in segments:
                    seg_start = seg.get("start", 0)
                    seg_end = seg.get("end", 0)
                    if seg_start >= clip_start and seg_end <= clip_end:
                        seg_text = seg.get("text", "")
                        words = seg_text.split()
                        seg_dur = seg_end - seg_start
                        for wi, w in enumerate(words):
                            w_start = seg_start + (wi / max(1, len(words))) * seg_dur - clip_start
                            w_end = seg_start + ((wi + 1) / max(1, len(words))) * seg_dur - clip_start
                            word_timestamps_list.append({
                                "word": w,
                                "start": round(max(0, w_start), 3),
                                "end": round(max(0, w_end), 3),
                            })

            clip = Clip(
                rank=clip_data.get("rank", i + 1),
                start_time=clip_data["start"],
                end_time=clip_data["end"],
                duration=clip_data["duration"],
                viral_score=clip_data.get("final_score", 0),
                title_suggestion=clip_data.get("title_suggestion", ""),
                hook_text=clip_data.get("hook_text", ""),
                reason=clip_data.get("reason", ""),
                file_path=clip_data.get("file_path", ""),
                file_path_landscape=clip_data.get("file_path_landscape", ""),
                scores_json=json.dumps(clip_data.get("scores", {})),
                project_id=project_id,
                # Speaker detection metadata (MediaPipe FaceMesh)
                sfcs_version=clip_data.get("sfcs_version", "director_v4"),
                sfcs_faces_detected=int(clip_data.get("sfcs_faces_detected", 0) or 0),
                sfcs_frames_with_speaker=int(clip_data.get("sfcs_frames_with_speaker", 0) or 0),
                sfcs_fallback_frames=int(clip_data.get("sfcs_fallback_frames", 0) or 0),
                # Caption engine data
                word_timestamps=json.dumps(word_timestamps_list),
            )
            db.add(clip)

        # ─── Step 7: Generate Video Summary ───────────────────────
        _update_project(
            db, project_id,
            progress=97,
            status_message="Generating video summary...",
        )
        try:
            _generate_video_summary(segments, project, project_folder, storage)
        except Exception as summary_err:
            logger.warning(f"Video summary generation failed (non-fatal): {summary_err}")

        # ─── Done ───────────────────────────────────────────────
        total_time = time.perf_counter() - pipeline_start
        _update_project(
            db, project_id,
            **_build_completion_project_update(
                clip_count=len(generated_clips),
                total_time=total_time,
                transcribe_time=transcribe_time,
                ai_time=ai_time,
                speaker_time=speaker_time,
                clip_gen_time=clip_gen_time,
            ),
        )
        db.commit()

        # Clean up temp audio file
        # try:
        #     abs_audio = storage.get_absolute_path(audio_path)
        #     if os.path.exists(abs_audio):
        #         os.remove(abs_audio)
        # except Exception:
        #     pass

        # Clean speaker cache for this video to free memory
        if speaker_service:
            speaker_service.clear_cache(video.file_path)

        # Enforce 100GB storage limit
        try:
            storage.enforce_storage_limit()
        except Exception as limit_err:
            logger.error(f"Failed to enforce storage limit: {limit_err}")

        logger.info(
            f"Pipeline complete for project {project_id}: "
            f"{len(generated_clips)} clips in {total_time:.0f}s"
        )

    except Exception as e:
        logger.error(f"Pipeline failed for project {project_id}: {traceback.format_exc()}")
        with open("celery_error.log", "a") as f:
            f.write(f"\n{'='*80}\nProject: {project_id}\n{traceback.format_exc()}\n")
        _update_project(
            db, project_id,
            status=ProjectStatus.FAILED,
            error_message=_normalize_pipeline_error_message(e),
            status_message="Processing failed. Please try again.",
        )
        raise

    finally:
        if project_lock:
            project_lock.release()
        db.close()
