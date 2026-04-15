"""
NexClip — Captions API Endpoints
Style listing, caption application, and status polling.
"""

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Clip
from app.api.auth import get_current_user
from app.db.models import User
from app.schemas import (
    CaptionStyleResponse, ApplyCaptionRequest, CaptionStatusResponse,
)

router = APIRouter(tags=["Captions"])

API_BASE = ""  # Set dynamically


# ── List all caption styles ─────────────────────────────────────
@router.get("/api/captions/styles", response_model=list[CaptionStyleResponse])
def list_caption_styles():
    """Return all 12 available caption styles."""
    from app.captions.style_registry import get_all_styles
    styles = get_all_styles()
    return [
        CaptionStyleResponse(
            style_id=s.style_id,
            display_name=s.display_name,
            font_size=s.font_size,
            word_by_word=s.word_by_word,
            glow=s.glow,
        )
        for s in styles
    ]


# ── Apply caption style to a clip ──────────────────────────────
@router.post("/api/clips/{clip_id}/apply-caption-style")
def apply_caption_style(
    clip_id: str,
    request: ApplyCaptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue a caption rendering job for a clip."""
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if request.style_id == "NONE":
        clip.caption_style_id = ""
        clip.caption_status = "none"
        clip.captioned_video_url = ""
        clip.captioned_video_url_landscape = ""
        db.commit()
        return {
            "message": "Captions removed from clip",
            "clip_id": clip.id,
            "style_id": "NONE",
            "status": "none",
        }

    # Validate style
    from app.captions.style_registry import get_style
    style = get_style(request.style_id)
    if not style:
        raise HTTPException(status_code=400, detail=f"Unknown style: {request.style_id}")

    # Update status
    clip.caption_style_id = request.style_id
    clip.caption_status = "processing"
    db.commit()

    # Queue Celery task
    try:
        from app.workers.caption_tasks import apply_caption_style_task
        apply_caption_style_task.delay(clip.id, request.style_id, request.active_aspect)
    except Exception as e:
        clip.caption_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue caption task: {e}")

    return {
        "message": f"Caption style '{style.display_name}' queued for clip",
        "clip_id": clip.id,
        "style_id": request.style_id,
        "status": "processing",
    }


# ── Poll caption rendering status ─────────────────────────────
@router.get("/api/clips/{clip_id}/caption-status", response_model=CaptionStatusResponse)
def get_caption_status(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check the status of caption rendering for a clip."""
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    return CaptionStatusResponse(
        clip_id=clip.id,
        caption_status=clip.caption_status or "none",
        caption_style_id=clip.caption_style_id or "",
        captioned_video_url=clip.captioned_video_url or "",
    )


# ── Apply caption style to ALL clips in a project ─────────────
@router.post("/api/projects/{project_id}/apply-caption-all")
def apply_caption_style_to_all(
    project_id: str,
    request: ApplyCaptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue a caption rendering job for ALL clips in a project sequentially."""
    from app.db.models import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.clips:
        raise HTTPException(status_code=400, detail="Project has no clips")

    # If NONE, just clear them synchronously
    if request.style_id == "NONE":
        for clip in project.clips:
            clip.caption_style_id = ""
            clip.caption_status = "none"
            clip.captioned_video_url = ""
            clip.captioned_video_url_landscape = ""
        db.commit()
        return {
            "message": f"Captions removed from {len(project.clips)} clips",
            "project_id": project_id,
            "clips_count": len(project.clips),
            "style_id": "NONE",
        }

    # Validate style
    from app.captions.style_registry import get_style
    style = get_style(request.style_id)
    if not style:
        raise HTTPException(status_code=400, detail=f"Unknown style: {request.style_id}")

    # Queue Celery task for each clip
    queued_count = 0
    try:
        from app.workers.caption_tasks import apply_caption_style_task
        for clip in project.clips:
            # Update status
            clip.caption_style_id = request.style_id
            clip.caption_status = "processing"
            db.commit()
            
            # Queue task
            apply_caption_style_task.delay(clip.id, request.style_id, request.active_aspect)
            queued_count += 1
            
    except Exception as e:
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to queue caption tasks: {e}")

    return {
        "message": f"Caption style '{style.display_name}' queued for {queued_count} clips",
        "project_id": project_id,
        "style_id": request.style_id,
        "clips_queued": queued_count,
        "status": "processing",
    }

