"""
NexClip — Projects API endpoints.
Upload videos, check status, list projects, get clips.
"""

import uuid
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from typing import Optional, List

from app.db.database import get_db
from app.db.models import Project, Video, Clip, ProjectStatus
from app.schemas import (
    ProjectCreate, ProjectResponse, ProjectDetailResponse,
    VideoURLRequest, VideoResponse, ClipResponse,
    ProjectStatusResponse, ClipDownloadResponse,
)
from app.api.auth import get_current_user
from app.db.models import User
from app.services.clip_dedup import dedupe_clip_records
from app.services.storage_service import get_storage

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _normalize_project_status_message(status_message: str, clip_count: int) -> str:
    if not status_message:
        return status_message

    if status_message.startswith("Complete!") and " clips generated" in status_message:
        return re.sub(
            r"^Complete!\s+\d+\s+clips generated",
            f"Complete! {clip_count} clips generated",
            status_message,
            count=1,
        )

    return status_message


def _effective_project_clip_count(project: Project) -> int:
    if not project.clips:
        return project.clip_count
    return len(dedupe_clip_records(project.clips))


def _build_project_response(project: Project) -> ProjectResponse:
    payload = ProjectResponse.model_validate(project)
    payload.clip_count = _effective_project_clip_count(project)
    payload.status_message = _normalize_project_status_message(payload.status_message, payload.clip_count)
    return payload


def _build_project_detail_response(project: Project) -> ProjectDetailResponse:
    payload = ProjectDetailResponse.model_validate(project)
    payload.clips = [ClipResponse.model_validate(c) for c in dedupe_clip_records(project.clips)]
    payload.clip_count = len(payload.clips) or project.clip_count
    payload.status_message = _normalize_project_status_message(payload.status_message, payload.clip_count)
    return payload


# ── Create project with file upload ─────────────────────────────
@router.post("/upload", response_model=ProjectResponse, status_code=201)
async def create_project_upload(
    title: str = Form(...),
    description: str = Form(""),
    clip_count: int = Form(10),
    client_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate file type
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    # Create project
    project = Project(
        title=title,
        description=description,
        clip_count=min(max(clip_count, 1), 50),
        client_id=client_id,
        owner_id=current_user.id,
        status=ProjectStatus.UPLOADED,
        status_message="Video uploaded successfully",
    )
    db.add(project)
    db.flush()

    # Save file via storage abstraction
    storage = get_storage()
    safe_title = re.sub(r'[\\/*?:"<>| ]', '_', project.title)
    directory = f"{safe_title}_{project.id[:8]}/upload"
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "mp4"
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = await storage.save_upload(file, directory, filename)

    # Create video record
    video = Video(
        original_filename=file.filename or "video.mp4",
        file_path=file_path,
        source_type="upload",
        mime_type=file.content_type or "",
        project_id=project.id,
    )
    db.add(video)
    db.commit()
    db.refresh(project)

    # Enqueue processing task
    try:
        from app.workers.tasks import process_video_task
        process_video_task.delay(project.id)
    except Exception as e:
        project.status_message = f"Uploaded but worker unavailable: {e}"
        db.commit()

    return ProjectResponse.model_validate(project)


# ── Create project from URL ─────────────────────────────────────
@router.post("/url", response_model=ProjectResponse, status_code=201)
async def create_project_url(
    payload: VideoURLRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = Project(
        title=payload.title or "Untitled Project",
        clip_count=min(max(payload.clip_count or 10, 1), 50),
        client_id=payload.client_id,
        owner_id=current_user.id,
        status=ProjectStatus.UPLOADED,
        status_message="URL received, downloading...",
    )
    db.add(project)
    db.flush()

    video = Video(
        source_url=payload.url,
        source_type="youtube" if "youtube" in payload.url or "youtu.be" in payload.url else "url",
        file_path="",  # Will be set after download
        project_id=project.id,
    )
    db.add(video)
    db.commit()
    db.refresh(project)

    # Enqueue processing task
    try:
        from app.workers.tasks import process_video_task
        process_video_task.delay(project.id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        project.status_message = f"Failed to enqueue task: {e}"
        db.commit()

    return ProjectResponse.model_validate(project)


# ── List user projects ──────────────────────────────────────────
@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    projects = (
        db.query(Project)
        .filter(Project.owner_id == current_user.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    return [_build_project_response(p) for p in projects]


# ── Get project detail (with clips) ────────────────────────────
@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _build_project_detail_response(project)


# ── Get project status (for polling) ───────────────────────────
@router.get("/{project_id}/status", response_model=ProjectStatusResponse)
def get_project_status(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    clip_count = _effective_project_clip_count(project)
    return ProjectStatusResponse(
        project_id=project.id,
        status=project.status.value,
        progress=project.progress,
        status_message=_normalize_project_status_message(project.status_message, clip_count),
        error_message=project.error_message,
    )


# ── Get clips for a project ────────────────────────────────────
@router.get("/{project_id}/clips", response_model=List[ClipResponse])
def get_clips(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return [ClipResponse.model_validate(c) for c in dedupe_clip_records(project.clips)]


# ── Delete project ──────────────────────────────────────────────
@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Do NOT clean up files as per user request
    # storage = get_storage()
    # if project.video and project.video.file_path:
    #     await storage.delete_file(project.video.file_path)
    # for clip in project.clips:
    #     if clip.file_path:
    #         await storage.delete_file(clip.file_path)

    db.delete(project)
    db.commit()
