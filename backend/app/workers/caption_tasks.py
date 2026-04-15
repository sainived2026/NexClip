"""
NexClip — Caption Celery Task
Background task for applying caption styles to clips.
Features: caching (skip re-render), separate captioned/ directory.
"""

import json
import os
import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="captions.apply_style", bind=True, max_retries=2, autoretry_for=(Exception,), retry_backoff=True)
def apply_caption_style_task(self, clip_id: str, style_id: str, active_aspect: str = "9:16"):
    """
    Apply a caption style to BOTH aspect ratios of a clip's video file.
    
    Features:
    - Prioritizes the active_aspect (the one the user is currently viewing).
    - Caching: skips re-render if output file already exists.
    - Separate directory: captioned clips stored in captioned/ subdirectory.
    """
    from app.db.database import SessionLocal
    from app.db.models import Clip

    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            logger.error(f"Clip {clip_id} not found")
            return {"success": False, "error": "Clip not found"}

        # Update status
        clip.caption_status = "processing"
        db.commit()

        self.update_state(state="PROGRESS", meta={"pct": 10, "msg": "Loading caption engine..."})

        # Get word timestamps
        word_timestamps = []
        if clip.word_timestamps:
            try:
                word_timestamps = json.loads(clip.word_timestamps)
            except (json.JSONDecodeError, TypeError):
                pass

        if not word_timestamps:
            clip.caption_status = "failed"
            db.commit()
            logger.warning(f"No word timestamps for clip {clip_id}")
            return {"success": False, "error": "No word timestamps"}

        from app.core.config import get_settings
        settings = get_settings()

        # Build processing order: active aspect FIRST, then the other
        tasks_to_run = []
        
        if active_aspect == "16:9":
            order = [("16:9", clip.file_path_landscape), ("9:16", clip.file_path)]
        else:
            order = [("9:16", clip.file_path), ("16:9", clip.file_path_landscape)]
            
        for aspect, rel_path in order:
            if not rel_path:
                continue
            input_path = rel_path
            if not os.path.exists(input_path):
                input_path = os.path.join(settings.STORAGE_LOCAL_ROOT, rel_path)
            if os.path.exists(input_path):
                tasks_to_run.append((aspect, input_path))
                
        if not tasks_to_run:
            clip.caption_status = "failed"
            db.commit()
            return {"success": False, "error": "No video files found for clip"}
            
        from app.captions.caption_pipeline import apply_caption_style

        for i, (aspect, input_path) in enumerate(tasks_to_run):
            clip_dir = os.path.dirname(input_path)
            project_dir = os.path.dirname(clip_dir)
            captioned_dir = os.path.join(project_dir, "captioned")
            os.makedirs(captioned_dir, exist_ok=True)
            
            output_filename = f"{os.path.splitext(os.path.basename(input_path))[0]}_captioned_{style_id}.mp4"
            output_path = os.path.join(captioned_dir, output_filename)
            
            # Caching check
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Caption cache HIT for clip {clip_id} ({aspect}) style={style_id}")
                rel_out = os.path.relpath(output_path, "storage").replace("\\", "/")
                if aspect == "9:16":
                    clip.captioned_video_url = rel_out
                else:
                    clip.captioned_video_url_landscape = rel_out
                # After the FIRST (active) aspect is done, mark status as 'done' immediately
                if i == 0:
                    clip.caption_status = "done"
                    clip.caption_style_id = style_id
                db.commit()
                continue
                
            self.update_state(state="PROGRESS", meta={"pct": 30 + (i*30), "msg": f"Rendering {style_id} ({aspect})..."})
            
            def progress_cb(pct, msg, current_i=i):
                base_pct = 30 + (current_i * 30)
                self.update_state(state="PROGRESS", meta={"pct": base_pct + int(pct * 0.3), "msg": msg})
                
            res = apply_caption_style(
                input_video_path=input_path,
                word_timestamps=word_timestamps,
                style_id=style_id,
                output_path=output_path,
                progress_callback=progress_cb,
            )
            
            if res.get("success"):
                rel_out = os.path.relpath(output_path, "storage").replace("\\", "/")
                if aspect == "9:16":
                    clip.captioned_video_url = rel_out
                else:
                    clip.captioned_video_url_landscape = rel_out
                # After the FIRST (active) aspect is done, mark status as 'done' immediately
                # so the frontend can stop polling and show the captioned clip instantly.
                # The second aspect ratio will render silently in the background.
                if i == 0:
                    clip.caption_status = "done"
                    clip.caption_style_id = style_id
                db.commit()
                logger.info(f"Caption applied to clip {clip_id} ({aspect}): style={style_id}")
            else:
                logger.error(f"Caption failed for clip {clip_id} ({aspect}): {res.get('error', 'unknown')}")
                if i == 0:
                    # Only mark failed if the ACTIVE aspect fails
                    clip.caption_status = "failed"
                    db.commit()
                    return {"success": False, "error": res.get("error", "unknown")}

        # Final commit (ensures the second aspect ratio URL is saved)
        db.commit()
        
        return {"success": True, "style_id": style_id, "active_aspect": active_aspect}

    except Exception as e:
        logger.error(f"Caption task failed for clip {clip_id}: {e}", exc_info=True)
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip:
                clip.caption_status = "failed"
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
