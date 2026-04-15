"""
Nex Agent — Storage & Project Search Tools
=============================================
Smart project/clip search with duplicate disambiguation.
Provides: search_projects, project_detail, list_clips, get_clip_paths.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

from loguru import logger


def _get_storage_root() -> Path:
    """Get the absolute path to the NexClip storage root."""
    # Try from env
    root = os.environ.get("STORAGE_LOCAL_ROOT", "./storage")
    base = Path(__file__).resolve().parent.parent.parent / "backend"
    p = (base / root).resolve()
    if p.exists():
        return p
    # Fallback
    alt = Path(__file__).resolve().parent.parent.parent / "backend" / "storage"
    alt.mkdir(parents=True, exist_ok=True)
    return alt


def _get_db():
    """Get a DB session (lazy import to avoid circular deps)."""
    try:
        import sys
        backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        from app.db.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.warning(f"Could not get DB session: {e}")
        return None


def _search_projects_impl(query: str) -> List[Dict[str, Any]]:
    """
    Search for projects by name across the DB and storage folders.
    Returns list of matches with full metadata for disambiguation.
    """
    query_lower = query.lower().strip()
    results = []

    # Method 1: Search the database
    db = _get_db()
    if db:
        try:
            from app.db.models import Project, Clip
            projects = db.query(Project).all()
            for proj in projects:
                title = proj.title or ""
                if query_lower in title.lower():
                    clip_count = db.query(Clip).filter(Clip.project_id == proj.id).count()
                    results.append({
                        "source": "database",
                        "project_id": proj.id,
                        "title": title,
                        "folder": f"{re.sub(r'[\\\\/*?:\"<>| ]', '_', title)}_{proj.id[:8]}",
                        "status": str(proj.status.value) if proj.status else "unknown",
                        "clip_count": clip_count,
                        "created_at": str(proj.created_at) if proj.created_at else "",
                        "progress": proj.progress or 0,
                        "status_message": proj.status_message or "",
                    })
        except Exception as e:
            logger.warning(f"DB search failed: {e}")
        finally:
            db.close()

    # Method 2: Search storage folders directly
    storage_root = _get_storage_root()
    if storage_root.exists():
        for folder in storage_root.iterdir():
            if not folder.is_dir():
                continue
            folder_name = folder.name.lower()
            # Match the query against folder name (which is {SafeTitle}_{id[:8]})
            if query_lower in folder_name:
                # Check if already found in DB results
                already = any(r.get("folder", "").lower() == folder.name.lower() for r in results)
                if already:
                    # Enrich DB result with storage info
                    for r in results:
                        if r.get("folder", "").lower() == folder.name.lower():
                            r["storage_path"] = str(folder)
                            r["storage_size_mb"] = round(
                                sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e6, 1
                            )
                            # Count actual clip files
                            clip_files = list(folder.glob("clips/*.mp4")) + list(folder.glob("clips_portrait/*.mp4"))
                            r["clip_files_on_disk"] = len(clip_files)
                            # Check for summary
                            summary_file = folder / "summary" / "summary.json"
                            r["has_summary"] = summary_file.exists()
                    continue

                # Storage-only project (not in DB or name didn't match DB)
                clip_files = list(folder.glob("clips/*.mp4")) + list(folder.glob("clips_portrait/*.mp4"))
                size_mb = round(
                    sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e6, 1
                )
                modified = datetime.fromtimestamp(folder.stat().st_mtime).isoformat()
                results.append({
                    "source": "storage_only",
                    "title": folder.name.rsplit("_", 1)[0].replace("_", " ") if "_" in folder.name else folder.name,
                    "folder": folder.name,
                    "storage_path": str(folder),
                    "storage_size_mb": size_mb,
                    "clip_files_on_disk": len(clip_files),
                    "last_modified": modified,
                    "has_summary": (folder / "summary" / "summary.json").exists(),
                })

    return results


def _project_detail_impl(project_id: str) -> Dict[str, Any]:
    """Get full detail for a project by ID."""
    db = _get_db()
    if not db:
        return {"error": "Cannot access database"}

    try:
        from app.db.models import Project, Video, Clip, Transcript
        proj = db.query(Project).filter(Project.id == project_id).first()
        if not proj:
            return {"error": f"Project {project_id} not found"}

        video = proj.video
        clips = db.query(Clip).filter(Clip.project_id == project_id).order_by(Clip.rank).all()
        transcript = db.query(Transcript).filter(Transcript.project_id == project_id).first()

        safe_title = re.sub(r'[\\/*?:"<>| ]', '_', proj.title or "")
        folder = f"{safe_title}_{proj.id[:8]}"
        storage_root = _get_storage_root()
        folder_path = storage_root / folder

        return {
            "project_id": proj.id,
            "title": proj.title,
            "folder": folder,
            "folder_exists": folder_path.exists(),
            "status": str(proj.status.value) if proj.status else "unknown",
            "progress": proj.progress or 0,
            "status_message": proj.status_message or "",
            "created_at": str(proj.created_at) if proj.created_at else "",
            "video": {
                "source_url": video.source_url if video else None,
                "original_filename": video.original_filename if video else None,
                "duration_seconds": video.duration_seconds if video else None,
                "file_path": video.file_path if video else None,
            } if video else None,
            "transcript": {
                "file_path": transcript.file_path if transcript else None,
                "word_count": transcript.word_count if transcript else 0,
            } if transcript else None,
            "clips": [
                {
                    "id": c.id,
                    "rank": c.rank,
                    "title_suggestion": c.title_suggestion,
                    "hook_text": c.hook_text,
                    "viral_score": c.viral_score,
                    "duration": c.duration,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "file_path": c.file_path,
                    "file_path_landscape": c.file_path_landscape,
                    "has_captions": bool(c.captioned_file_path) if hasattr(c, "captioned_file_path") else False,
                }
                for c in clips
            ],
            "clip_count": len(clips),
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


def _list_clips_impl(project_id: str, sort_by: str = "rank") -> List[Dict[str, Any]]:
    """List clips for a project, sorted by rank or viral_score."""
    db = _get_db()
    if not db:
        return []

    try:
        from app.db.models import Clip
        query = db.query(Clip).filter(Clip.project_id == project_id)
        if sort_by == "viral_score":
            query = query.order_by(Clip.viral_score.desc())
        else:
            query = query.order_by(Clip.rank)

        clips = query.all()
        return [
            {
                "id": c.id,
                "rank": c.rank,
                "title_suggestion": c.title_suggestion,
                "hook_text": c.hook_text,
                "viral_score": c.viral_score,
                "duration": c.duration,
                "file_path": c.file_path,
                "file_path_landscape": getattr(c, "file_path_landscape", None),
            }
            for c in clips
        ]
    except Exception as e:
        logger.error(f"list_clips failed: {e}")
        return []
    finally:
        db.close()


def _get_clip_paths_impl(
    project_id: str, top_n: int = 2, aspect: str = "portrait"
) -> List[Dict[str, Any]]:
    """
    Get absolute file paths for the top N clips of a project.
    aspect: 'portrait' or 'landscape'
    """
    db = _get_db()
    if not db:
        return []

    try:
        from app.db.models import Clip
        clips = (
            db.query(Clip)
            .filter(Clip.project_id == project_id)
            .order_by(Clip.viral_score.desc())
            .limit(top_n)
            .all()
        )

        storage_root = _get_storage_root()
        result = []
        for c in clips:
            rel_path = c.file_path if aspect == "portrait" else (
                getattr(c, "file_path_landscape", None) or c.file_path
            )
            abs_path = str((storage_root / rel_path).resolve()) if rel_path else ""
            result.append({
                "clip_id": c.id,
                "rank": c.rank,
                "viral_score": c.viral_score,
                "title_suggestion": c.title_suggestion,
                "relative_path": rel_path,
                "absolute_path": abs_path,
                "file_exists": os.path.exists(abs_path) if abs_path else False,
                "duration": c.duration,
            })
        return result
    except Exception as e:
        logger.error(f"get_clip_paths failed: {e}")
        return []
    finally:
        db.close()


def _get_video_summary_impl(project_id: str) -> Dict[str, Any]:
    """Get or load the video summary for a project."""
    db = _get_db()
    if not db:
        return {"error": "Cannot access database"}

    try:
        from app.db.models import Project
        proj = db.query(Project).filter(Project.id == project_id).first()
        if not proj:
            return {"error": f"Project {project_id} not found"}

        safe_title = re.sub(r'[\\/*?:"<>| ]', '_', proj.title or "")
        folder = f"{safe_title}_{proj.id[:8]}"
        summary_path = _get_storage_root() / folder / "summary" / "summary.json"

        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {
                "project_id": project_id,
                "title": proj.title,
                "summary": None,
                "note": "Summary not yet generated. Process the video first.",
            }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════
#  REGISTRATION
# ══════════════════════════════════════════════════════════════

def register(executor: "ToolExecutor") -> int:
    """Register storage/project search tools with the Nex Agent tool executor."""

    executor.register_tool(
        name="nex_search_projects",
        description=(
            "Search for NexClip projects by name or keyword. "
            "Returns all matches with metadata (title, folder, status, clip count, "
            "created date, size) so the user can disambiguate duplicates. "
            "Example: nex_search_projects(query='Test 1')"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Project name or keyword to search for",
                },
            },
            "required": ["query"],
        },
        handler=lambda query="": json.dumps(_search_projects_impl(query), indent=2),
        category="storage",
    )

    executor.register_tool(
        name="nex_project_detail",
        description=(
            "Get full details for a specific project by its ID. "
            "Returns video info, transcript, all clips with scores and paths, "
            "storage folder info, and summary availability."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "The project UUID",
                },
            },
            "required": ["project_id"],
        },
        handler=lambda project_id="": json.dumps(
            _project_detail_impl(project_id), indent=2
        ),
        category="storage",
    )

    executor.register_tool(
        name="nex_list_clips",
        description=(
            "List all clips for a project, optionally sorted by rank or viral_score. "
            "Returns clip IDs, titles, scores, durations, and file paths."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
                "sort_by": {
                    "type": "string",
                    "enum": ["rank", "viral_score"],
                    "description": "Sort order (default: rank)",
                },
            },
            "required": ["project_id"],
        },
        handler=lambda project_id="", sort_by="rank": json.dumps(
            _list_clips_impl(project_id, sort_by), indent=2
        ),
        category="storage",
    )

    executor.register_tool(
        name="nex_get_clip_paths",
        description=(
            "Get absolute file paths for the top N clips of a project "
            "(sorted by viral score descending). Use aspect='portrait' for "
            "9:16 clips or 'landscape' for 16:9."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
                "top_n": {
                    "type": "integer",
                    "description": "Number of top clips to return (default: 2)",
                },
                "aspect": {
                    "type": "string",
                    "enum": ["portrait", "landscape"],
                    "description": "Aspect ratio preference (default: portrait)",
                },
            },
            "required": ["project_id"],
        },
        handler=lambda project_id="", top_n=2, aspect="portrait": json.dumps(
            _get_clip_paths_impl(project_id, int(top_n), aspect), indent=2
        ),
        category="storage",
    )

    executor.register_tool(
        name="nex_get_summary",
        description=(
            "Get the video summary for a project. "
            "Returns the AI-generated brief summary of the source video content."
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project UUID"},
            },
            "required": ["project_id"],
        },
        handler=lambda project_id="": json.dumps(
            _get_video_summary_impl(project_id), indent=2
        ),
        category="storage",
    )

    return 5  # 5 tools registered
