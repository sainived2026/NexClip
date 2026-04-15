"""
NexClip — Clips API endpoints.
Regenerate clips with different styles, export clips.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
import logging

from app.db.database import get_db
from app.db.models import Clip, Project, Video, Transcript
from app.api.auth import get_current_user
from app.db.models import User
from app.services.ffmpeg_service import FFmpegService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clips", tags=["Clips"])

class ClipExportRequest(BaseModel):
    preset_id: str

class ClipExportResponse(BaseModel):
    id: str
    file_path: str
    message: str

@router.post("/{clip_id}/export", response_model=ClipExportResponse)
async def export_clip(
    clip_id: str,
    payload: ClipExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    project = db.query(Project).filter(Project.id == clip.project_id, Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to access this clip's project")

    video = project.video
    if not video or not video.file_path:
        raise HTTPException(status_code=400, detail="Video file missing for this clip")

    # Build clip data dictionary required by FFmpegService
    clip_data = {
        "start": clip.start_time,
        "end": clip.end_time,
        "rank": clip.rank,
    }

    try:
        ffmpeg_service = FFmpegService()
        src_dimensions = ffmpeg_service._get_video_dimensions(video.file_path)
        
        # This is a synchronous call. A single generation usually takes 5-10s.
        new_file_path = ffmpeg_service.generate_clip(
            video_path=video.file_path,
            clip_data=clip_data,
            project_id=project.id,
            src_dimensions=src_dimensions,
            preset_id=payload.preset_id
        )

        # Update the clip to point to the newly rendered file
        # In a real system, you might want to create a new record or a version,
        # but replacing the file_path directly enables the frontend to just download the new video.
        clip.file_path = new_file_path
        db.commit()

        return ClipExportResponse(
            id=clip.id,
            file_path=new_file_path,
            message=f"Clip successfully exported with preset '{payload.preset_id}'"
        )
    except Exception as e:
        logger.error(f"Error exporting clip {clip_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
