"""
NexClip — Admin Panel API
Complete system management: configuration, status monitoring,
user management, AI prompt editing, and service control.

Security: Only the first registered user (admin/owner) can access these endpoints.
"""

import os
import re
import json
import time
import shutil
import subprocess
import platform
import sys
import psutil
import httpx
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from app.db.database import get_db
from app.db.models import User, Project, Video, Transcript, Clip, ProjectStatus
from app.api.auth import get_current_user
from app.core.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/admin", tags=["Admin"])

# ── Startup timestamp for uptime tracking ────────────────────────
_STARTUP_TIME = time.time()

# Track whether a restart is needed after config changes
_restart_required = False
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _BACKEND_ROOT.parent


# ══════════════════════════════════════════════════════════════════
# SECURITY: Admin-only access guard
# ══════════════════════════════════════════════════════════════════

def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Admin access guard. Since login is bypassed, everyone has admin rights.
    """
    return current_user


# ══════════════════════════════════════════════════════════════════
# 1. SYSTEM STATUS
# ══════════════════════════════════════════════════════════════════

@router.get("/status")
def get_system_status(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Live system health dashboard data.
    Returns status of all services, disk usage, project stats, etc.
    """
    # Backend is obviously running if we're here
    backend_status = "online"

    # Check Redis
    redis_status = "offline"
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        redis_status = "online"
    except Exception:
        pass

    # Check Celery by inspecting local worker processes to avoid broker stalls
    celery_status = "offline"
    active_tasks = 0
    try:
        celery_processes = _find_service_processes("celery")
        if celery_processes:
            celery_status = "online"
            active_tasks = len(celery_processes)
    except Exception:
        pass

    # Disk usage for storage directory
    storage_path = Path(settings.STORAGE_LOCAL_ROOT).resolve()
    disk_usage = {}
    try:
        total, used, free = shutil.disk_usage(storage_path)
        disk_usage = {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "usage_percent": round((used / total) * 100, 1),
        }
    except Exception:
        pass

    # Storage folder sizes
    storage_sizes = {}
    try:
        for subdir in ["uploads", "clips", "transcripts", "audio", "temp"]:
            folder = storage_path / subdir
            if folder.exists():
                size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
                storage_sizes[subdir] = round(size / (1024**2), 1)  # MB
            else:
                storage_sizes[subdir] = 0
    except Exception:
        pass

    # Database stats
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_projects = db.query(func.count(Project.id)).scalar() or 0
    total_clips = db.query(func.count(Clip.id)).scalar() or 0
    active_projects = db.query(func.count(Project.id)).filter(
        Project.status.in_([ProjectStatus.TRANSCRIBING, ProjectStatus.ANALYZING, ProjectStatus.GENERATING_CLIPS])
    ).scalar() or 0
    failed_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.FAILED
    ).scalar() or 0
    completed_projects = db.query(func.count(Project.id)).filter(
        Project.status == ProjectStatus.COMPLETED
    ).scalar() or 0

    # Uptime
    uptime_seconds = int(time.time() - _STARTUP_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    return {
        "services": {
            "backend": backend_status,
            "celery": celery_status,
            "redis": redis_status,
        },
        "active_tasks": active_tasks,
        "uptime": uptime_str,
        "uptime_seconds": uptime_seconds,
        "disk": disk_usage,
        "storage_sizes_mb": storage_sizes,
        "stats": {
            "total_users": total_users,
            "total_projects": total_projects,
            "total_clips": total_clips,
            "active_projects": active_projects,
            "completed_projects": completed_projects,
            "failed_projects": failed_projects,
        },
        "restart_required": _restart_required,
        "platform": {
            "os": platform.system(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1) if psutil else None,
        },
    }


# ══════════════════════════════════════════════════════════════════
# 2. ENVIRONMENT CONFIGURATION
# ══════════════════════════════════════════════════════════════════

# Settings grouped by category for the frontend
CONFIG_SCHEMA = {
    "app": {
        "label": "Application",
        "fields": {
            "APP_NAME": {"type": "text", "label": "App Name"},
            "APP_ENV": {"type": "select", "label": "Environment", "options": ["development", "production"]},
            "SECRET_KEY": {"type": "password", "label": "Secret Key"},
            "ACCESS_TOKEN_EXPIRE_MINUTES": {"type": "number", "label": "Token Expiry (minutes)"},
            "CORS_ORIGINS": {"type": "text", "label": "CORS Origins (comma-separated)"},
        },
    },
    "database": {
        "label": "Database",
        "fields": {
            "DATABASE_URL": {"type": "text", "label": "Database URL"},
        },
    },
    "redis": {
        "label": "Redis",
        "fields": {
            "REDIS_URL": {"type": "text", "label": "Redis URL"},
        },
    },
    "storage": {
        "label": "Storage",
        "fields": {
            "STORAGE_MODE": {"type": "select", "label": "Storage Mode", "options": ["local", "s3"]},
            "STORAGE_LOCAL_ROOT": {"type": "text", "label": "Local Storage Path"},
            "MAX_UPLOAD_SIZE_MB": {"type": "number", "label": "Max Upload Size (MB)"},
            "S3_BUCKET_NAME": {"type": "text", "label": "S3 Bucket"},
            "S3_REGION": {"type": "text", "label": "S3 Region"},
            "AWS_ACCESS_KEY_ID": {"type": "password", "label": "AWS Access Key"},
            "AWS_SECRET_ACCESS_KEY": {"type": "password", "label": "AWS Secret Key"},
        },
    },
    "llm": {
        "label": "AI / LLM (Fallback Chain)",
        "fields": {
            "ANTHROPIC_API_KEY": {"type": "password", "label": "Anthropic API Key (Priority 1)"},
            "ANTHROPIC_MODEL": {"type": "text", "label": "Anthropic Model"},
            "OPENAI_API_KEY": {"type": "password", "label": "OpenAI API Key (Priority 2)"},
            "OPENAI_MODEL": {"type": "text", "label": "OpenAI Model"},
            "GEMINI_API_KEY": {"type": "password", "label": "Gemini API Key (Priority 3)"},
            "GEMINI_MODEL": {"type": "text", "label": "Gemini Model"},
            "OPENROUTER_API_KEY": {"type": "password", "label": "OpenRouter API Key (Priority 4)"},
            "OPENROUTER_MODEL": {"type": "text", "label": "OpenRouter Model"},
            "LLM_TIMEOUT": {"type": "number", "label": "LLM Timeout (sec)"},
            "LLM_MAX_TOKENS": {"type": "number", "label": "Max Tokens"},
            "LLM_TEMPERATURE": {"type": "number", "label": "Temperature", "step": 0.1},
            "LLM_MAX_TRANSCRIPT_LENGTH": {"type": "number", "label": "Max Transcript Length"},
        },
    },
    "stt": {
        "label": "Speech-to-Text",
        "fields": {
            "ELEVENLABS_API_KEY": {"type": "password", "label": "ElevenLabs API Key (Priority 1)"},
            "ELEVENLABS_STT_MODEL": {"type": "text", "label": "ElevenLabs STT Model"},
            "WHISPER_MODEL": {"type": "select", "label": "Whisper Model (Fallback)", "options": ["tiny", "base", "small", "medium", "large"]},
            "WHISPER_DEVICE": {"type": "select", "label": "Whisper Device", "options": ["cuda", "cpu"]},
            "WHISPER_COMPUTE_TYPE": {"type": "select", "label": "Compute Type", "options": ["float16", "int8", "float32"]},
        },
    },
    "video": {
        "label": "Video Output",
        "fields": {
            "OUTPUT_VIDEO_WIDTH": {"type": "number", "label": "Output Width (px)"},
            "OUTPUT_VIDEO_HEIGHT": {"type": "number", "label": "Output Height (px)"},
            "VIDEO_CODEC": {"type": "text", "label": "Video Codec"},
            "VIDEO_PRESET": {"type": "select", "label": "Encoding Preset", "options": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"]},
            "VIDEO_CRF": {"type": "number", "label": "CRF Quality (lower = better)"},
            "AUDIO_CODEC": {"type": "text", "label": "Audio Codec"},
            "AUDIO_BITRATE": {"type": "text", "label": "Audio Bitrate"},
            "AUDIO_SAMPLE_RATE": {"type": "number", "label": "Audio Sample Rate"},
            "CAPTION_FONT_SIZE": {"type": "number", "label": "Caption Font Size"},
            "CAPTION_MAX_LENGTH": {"type": "number", "label": "Caption Max Length"},
        },
    },
    "clips": {
        "label": "Clip Defaults",
        "fields": {
            "DEFAULT_CLIP_COUNT": {"type": "number", "label": "Default Clip Count"},
            "MIN_CLIP_DURATION": {"type": "number", "label": "Min Duration (sec)"},
            "MAX_CLIP_DURATION": {"type": "number", "label": "Max Duration (sec)"},
        },
    },
    "performance": {
        "label": "Performance",
        "fields": {
            "FFMPEG_PARALLEL_CLIPS": {"type": "number", "label": "Parallel Clips"},
            "FFMPEG_THREADS_PER_CLIP": {"type": "number", "label": "Threads per Clip"},
        },
    },
    "timeouts": {
        "label": "Timeouts",
        "fields": {
            "FFMPEG_CLIP_TIMEOUT": {"type": "number", "label": "FFmpeg Clip Timeout (sec)"},
            "FFMPEG_AUDIO_TIMEOUT": {"type": "number", "label": "FFmpeg Audio Timeout (sec)"},
            "AUDIO_LOAD_TIMEOUT": {"type": "number", "label": "Audio Load Timeout (sec)"},
            "DOWNLOAD_TIMEOUT": {"type": "number", "label": "Download Timeout (sec)"},
            "FFPROBE_TIMEOUT": {"type": "number", "label": "FFprobe Timeout (sec)"},
            "FFMPEG_DURATION_TIMEOUT": {"type": "number", "label": "FFmpeg Duration Timeout (sec)"},
        },
    },
    "speaker_detection": {
        "label": "Speaker Detection",
        "fields": {
            "SPEAKER_DETECTION_ENABLED": {"type": "select", "label": "Enabled", "options": ["true", "false"]},
            "SPEAKER_DETECTION_SAMPLE_FPS": {"type": "number", "label": "Sample FPS"},
            "SPEAKER_DETECTION_FRAME_WIDTH": {"type": "number", "label": "Frame Width (px)"},
        },
    },
    "captions": {
        "label": "Caption Engine",
        "fields": {
            "CAPTION_ENGINE_ENABLED": {"type": "select", "label": "Caption Engine Enabled", "options": ["true", "false"]},
            "CAPTION_DEFAULT_STYLE": {"type": "select", "label": "Default Caption Style", "options": [
                "opus_classic", "ghost_karaoke", "cinematic_lower", "allcaps_tracker",
                "underline_reveal", "serif_story", "mrbeast_bold", "linkedin_clean",
                "reels_standard", "prestige_serif", "highlighter_mark", "spaced_impact",
                "ghost_pill", "documentary_tag", "feather_light", "stroked_uppercase",
                "accent_line", "warm_serif_glow",
            ]},
            "CAPTION_WORDS_PER_SEGMENT": {"type": "number", "label": "Words per Segment"},
            "CAPTION_FONT_SEARCH_PATHS": {"type": "text", "label": "Font Search Paths"},
        },
    },
    "nex_agent": {
        "label": "Nex Agent",
        "fields": {
            "NEX_AGENT_ENABLED": {"type": "select", "label": "Nex Agent Enabled", "options": ["true", "false"]},
            "NEX_AGENT_PORT": {"type": "number", "label": "Nex Agent Port"},
            "NEX_AGENT_MEMORY_PATH": {"type": "text", "label": "Nex Agent Memory Path"},
        },
    },
    "nexearch": {
        "label": "Nexearch Intelligence Engine",
        "fields": {
            "NEXEARCH_ENABLED": {"type": "select", "label": "Nexearch Enabled", "options": ["true", "false"]},
            "NEXEARCH_APP_ENV": {"type": "select", "label": "Nexearch Environment", "options": ["development", "production"]},
            "NEXEARCH_LOG_LEVEL": {"type": "select", "label": "Log Level", "options": ["DEBUG", "INFO", "WARNING", "ERROR"]},
            "NEXEARCH_CLIENTS_DIR": {"type": "text", "label": "Clients Data Directory"},
            "NEXEARCH_APIFY_TOKEN": {"type": "password", "label": "Apify Token (Scraping)"},
            "NEXEARCH_FERNET_KEY": {"type": "password", "label": "Fernet Encryption Key"},
            "NEXEARCH_CORS_ORIGINS": {"type": "text", "label": "Nexearch CORS Origins"},
        },
    },
    "nexearch_evolution": {
        "label": "Nexearch Evolution",
        "fields": {
            "NEXEARCH_EVOLUTION_MAX_CHANGE_PERCENT": {"type": "number", "label": "Max Evolution Change %"},
            "NEXEARCH_EVOLUTION_MIN_POSTS_FOR_PATTERN": {"type": "number", "label": "Min Posts for Pattern"},
            "NEXEARCH_ENABLE_UNIVERSAL_EVOLUTION": {"type": "select", "label": "Universal Evolution", "options": ["true", "false"]},
        },
    },
    "arc_agent": {
        "label": "Arc Agent",
        "fields": {
            "NEXEARCH_ARC_AGENT_ENABLED": {"type": "select", "label": "Arc Agent Enabled", "options": ["true", "false"]},
            "NEXEARCH_ARC_AGENT_MODEL": {"type": "text", "label": "Arc Agent LLM Model"},
            "ARC_AGENT_PORT": {"type": "number", "label": "Arc Agent Port"},
            "ARC_AGENT_MEMORY_PATH": {"type": "text", "label": "Arc Agent Memory Path"},
            "ARC_AGENT_URL": {"type": "text", "label": "Arc Agent URL"},
        },
    },
    "agent_bridge": {
        "label": "Agent Communication",
        "fields": {
            "AGENT_BRIDGE_ENABLED": {"type": "select", "label": "Agent Bridge Enabled", "options": ["true", "false"]},
            "AGENT_BRIDGE_TIMEOUT_SECONDS": {"type": "number", "label": "Bridge Timeout (sec)"},
            "NEXEARCH_NEX_AGENT_ENABLED": {"type": "select", "label": "Nex Agent Integration", "options": ["true", "false"]},
            "NEXEARCH_NEX_AGENT_URL": {"type": "text", "label": "Nex Agent URL"},
        },
    },
}

# Keys that contain sensitive data — mask in GET responses
_SENSITIVE_KEYS = {
    "SECRET_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
    "OPENROUTER_API_KEY", "ELEVENLABS_API_KEY", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY", "NEXEARCH_APIFY_TOKEN", "NEXEARCH_FERNET_KEY",
}


def _sanitize_env_value(value: Optional[str]) -> str:
    """Normalize values loaded from or written to .env."""
    if value is None:
        return ""
    cleaned = str(value).strip()
    if " #" in cleaned:
        cleaned = cleaned.split(" #", 1)[0].rstrip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _read_env_file() -> Dict[str, str]:
    """Read the .env file and return as dict."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    values = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = _sanitize_env_value(value)
    return values


def _write_env_file(updates: Dict[str, str]):
    """Update specific keys in the .env file, preserving comments and structure."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        raise FileNotFoundError(".env file not found")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    updated_keys = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={_sanitize_env_value(updates[key])}")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Add any new keys that weren't in the file
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={_sanitize_env_value(value)}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive values for API responses."""
    if key in _SENSITIVE_KEYS and value:
        if len(value) <= 8:
            return "••••••••"
        return value[:4] + "••••" + value[-4:]
    return value


def _get_service_specs() -> Dict[str, Dict[str, Any]]:
    python_executable = _BACKEND_ROOT / "venv" / "Scripts" / "python.exe"
    if not python_executable.exists():
        python_executable = Path(sys.executable)

    detached_flags = 0
    if platform.system() == "Windows":
        detached_flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0)
        )

    return {
        "backend": {
            "label": "Backend API",
            "match": ["-m", "uvicorn", "app.main:app"],
            "command": [str(python_executable), "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            "cwd": _BACKEND_ROOT,
            "touch_path": _BACKEND_ROOT / "app" / "main.py",
            "reload_touch": True,
            "creationflags": detached_flags,
        },
        "celery": {
            "label": "Celery Worker",
            "match": ["-m", "celery", "-A", "app.workers.celery_app", "worker"],
            "command": [
                str(python_executable),
                "-m",
                "celery",
                "-A",
                "app.workers.celery_app",
                "worker",
                "-Q",
                "video,captions,nexearch,celery",
                "--loglevel=info",
                "--pool=threads",
                "--concurrency=8",
            ],
            "cwd": _BACKEND_ROOT,
            "creationflags": detached_flags,
        },
        "nex_agent": {
            "label": "Nex Agent",
            "match": ["-m", "nex_agent.server"],
            "command": [str(python_executable), "-m", "nex_agent.server"],
            "cwd": _REPO_ROOT,
            "creationflags": detached_flags,
        },
        "nexearch": {
            "label": "Nexearch Engine",
            "match": ["-m", "uvicorn", "nexearch.main:app"],
            "command": [str(python_executable), "-m", "uvicorn", "nexearch.main:app", "--reload", "--host", "0.0.0.0", "--port", "8002"],
            "cwd": _REPO_ROOT,
            "touch_path": _REPO_ROOT / "nexearch" / "main.py",
            "reload_touch": True,
            "creationflags": detached_flags,
        },
        "arc_agent": {
            "label": "Arc Agent",
            "match": ["-m", "nexearch.arc.server"],
            "command": [str(python_executable), "-m", "nexearch.arc.server"],
            "cwd": _REPO_ROOT,
            "creationflags": detached_flags,
        },
    }


def _service_env() -> Dict[str, str]:
    env = os.environ.copy()
    python_paths = [str(_REPO_ROOT), str(_BACKEND_ROOT)]
    existing = env.get("PYTHONPATH", "")
    if existing:
        python_paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    return env


def _restartable_services() -> List[str]:
    return [*list(_get_service_specs().keys()), "all"]


def _find_service_processes(service: str) -> List[psutil.Process]:
    spec = _get_service_specs()[service]
    processes: List[psutil.Process] = []

    for proc in psutil.process_iter(["pid", "cmdline", "exe"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            executable = proc.info.get("exe") or ""
            haystack = f"{executable} {cmdline}"
            if all(fragment in cmdline for fragment in spec["match"]) and "NexClip" in haystack:
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return processes


def _terminate_service_processes(service: str) -> int:
    processes = _find_service_processes(service)
    if not processes:
        return 0

    for proc in processes:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    _, alive = psutil.wait_procs(processes, timeout=5)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return len(processes)


def _spawn_service(service: str):
    spec = _get_service_specs()[service]
    service_env = _service_env()

    if platform.system() == "Windows":
        # Open a titled terminal with visible output (matches start.bat behavior)
        cwd = str(spec["cwd"]).replace("/", "\\")
        # Use relative venv activate path to avoid spaces-in-path issues
        if str(spec["cwd"]) == str(_BACKEND_ROOT):
            activate = ".\\venv\\Scripts\\activate"
        else:
            activate = ".\\backend\\venv\\Scripts\\activate"
        # Build module command using venv-activated python (drop full exe path)
        args = spec["command"][1:]
        inner_cmd = "python " + " ".join(str(a) for a in args)
        shell_cmd = (
            f'start "{spec["label"]}" cmd /k '
            f'"cd /d {cwd} && {activate} && set PYTHONPATH={service_env["PYTHONPATH"]} && {inner_cmd}"'
        )
        subprocess.Popen(shell_cmd, shell=True, env=service_env)
    else:
        popen_kwargs: Dict[str, Any] = {
            "cwd": str(spec["cwd"]),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "start_new_session": True,
            "env": service_env,
        }
        subprocess.Popen(spec["command"], **popen_kwargs)


def _restart_single_service(service: str) -> str:
    spec = _get_service_specs()[service]

    if spec.get("reload_touch") and _find_service_processes(service):
        spec["touch_path"].touch()
        return f"{spec['label']} reload triggered"

    if service != "backend":
        _terminate_service_processes(service)

    _spawn_service(service)
    return f"{spec['label']} restarted"


def _probe_http_service(service_name: str, port: int, url: str) -> tuple[str, Dict[str, Any]]:
    try:
        t0 = time.time()
        resp = httpx.get(url, timeout=1.5)
        latency = int((time.time() - t0) * 1000)
        if resp.status_code == 200:
            return service_name, {
                "status": "online",
                "port": port,
                "latency_ms": latency,
                "details": resp.json(),
            }
        return service_name, {"status": "offline", "port": port, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return service_name, {"status": "offline", "port": port, "error": str(e)[:100]}


@router.get("/config")
def get_config(admin: User = Depends(require_admin)):
    """Get all configuration settings grouped by category, with sensitive values masked."""
    env_values = _read_env_file()

    result = {}
    for category_key, category in CONFIG_SCHEMA.items():
        fields = {}
        for field_key, field_meta in category["fields"].items():
            raw_value = env_values.get(field_key, "")
            fields[field_key] = {
                **field_meta,
                "value": _mask_value(field_key, raw_value),
                "is_set": bool(raw_value),
            }
        result[category_key] = {
            "label": category["label"],
            "fields": fields,
        }

    return {"schema": result}


@router.put("/config")
def update_config(
    updates: Dict[str, str] = Body(...),
    admin: User = Depends(require_admin),
):
    """
    Update environment configuration.
    Accepts a flat dict of KEY=VALUE pairs.
    Writes to .env file and flags restart as required.
    """
    global _restart_required

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Validate keys — only allow known config keys
    all_valid_keys = set()
    for category in CONFIG_SCHEMA.values():
        all_valid_keys.update(category["fields"].keys())

    invalid_keys = set(updates.keys()) - all_valid_keys
    if invalid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown config keys: {', '.join(invalid_keys)}",
        )

    # Don't overwrite sensitive values with masked placeholder
    clean_updates = {}
    for key, value in updates.items():
        if "••••" in value:
            continue  # User didn't change this masked field
        clean_updates[key] = value

    if not clean_updates:
        return {"message": "No changes detected", "restart_required": _restart_required}

    try:
        _write_env_file(clean_updates)
        _restart_required = True
        logger.info(f"Admin updated config keys: {list(clean_updates.keys())}")
        return {
            "message": f"Updated {len(clean_updates)} setting(s). Restart required to apply.",
            "updated_keys": list(clean_updates.keys()),
            "restart_required": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")


# ══════════════════════════════════════════════════════════════════
# 3. AI SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════

def _get_prompt_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / "services" / "ai_scoring_service.py"


@router.get("/prompt")
def get_ai_prompt(admin: User = Depends(require_admin)):
    """Read the current AI system prompt from ai_scoring_service.py."""
    try:
        file_path = _get_prompt_file_path()
        content = file_path.read_text(encoding="utf-8")

        # Extract the prompt string between triple quotes
        match = re.search(
            r'CLIP_SELECTION_SYSTEM_PROMPT\s*=\s*"""(.*?)"""',
            content,
            re.DOTALL,
        )
        if match:
            return {"prompt": match.group(1).strip()}
        else:
            return {"prompt": "", "error": "Could not locate prompt in file"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read prompt: {e}")


@router.put("/prompt")
def update_ai_prompt(
    body: Dict[str, str] = Body(...),
    admin: User = Depends(require_admin),
):
    """Update the AI system prompt in ai_scoring_service.py."""
    global _restart_required

    new_prompt = body.get("prompt", "").strip()
    if not new_prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    try:
        file_path = _get_prompt_file_path()
        content = file_path.read_text(encoding="utf-8")

        # Replace the prompt between triple quotes
        new_content = re.sub(
            r'(CLIP_SELECTION_SYSTEM_PROMPT\s*=\s*""").*?(""")',
            lambda m: f'{m.group(1)}{new_prompt}{m.group(2)}',
            content,
            flags=re.DOTALL,
        )

        file_path.write_text(new_content, encoding="utf-8")
        _restart_required = True
        logger.info("Admin updated AI system prompt")

        return {"message": "AI prompt updated. Restart Celery to apply.", "restart_required": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update prompt: {e}")


# ══════════════════════════════════════════════════════════════════
# 4. USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════

@router.get("/users")
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """List all users with their project counts."""
    users = db.query(User).order_by(User.created_at.asc()).all()

    result = []
    for user in users:
        project_count = db.query(func.count(Project.id)).filter(Project.owner_id == user.id).scalar() or 0
        clip_count = (
            db.query(func.count(Clip.id))
            .join(Project, Clip.project_id == Project.id)
            .filter(Project.owner_id == user.id)
            .scalar() or 0
        )
        result.append({
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "project_count": project_count,
            "clip_count": clip_count,
            "is_admin": user.id == users[0].id if users else False,
        })

    return {"users": result}


@router.put("/users/{user_id}/toggle")
def toggle_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Activate/deactivate a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Don't allow deactivating the admin
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate the admin account")

    user.is_active = not user.is_active
    db.commit()

    status_str = "activated" if user.is_active else "deactivated"
    logger.info(f"Admin {status_str} user {user.email}")
    return {"message": f"User {status_str}", "is_active": user.is_active}


# ══════════════════════════════════════════════════════════════════
# 5. PROJECT MANAGEMENT
# ══════════════════════════════════════════════════════════════════

@router.get("/projects")
def list_all_projects(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """List all projects across all users with full details."""
    projects = (
        db.query(Project)
        .order_by(Project.created_at.desc())
        .limit(100)
        .all()
    )

    result = []
    for proj in projects:
        video = proj.video
        clip_count = db.query(func.count(Clip.id)).filter(Clip.project_id == proj.id).scalar() or 0
        result.append({
            "id": proj.id,
            "title": proj.title,
            "status": proj.status.value if proj.status else "UNKNOWN",
            "progress": proj.progress,
            "status_message": proj.status_message,
            "error_message": proj.error_message,
            "clip_count": clip_count,
            "owner_email": proj.owner.email if proj.owner else "Unknown",
            "owner_username": proj.owner.username if proj.owner else "Unknown",
            "video_filename": video.original_filename if video else None,
            "video_source_url": video.source_url if video else None,
            "video_duration": video.duration_seconds if video else None,
            "video_size_mb": round(video.file_size_bytes / (1024**2), 1) if video and video.file_size_bytes else None,
            "created_at": proj.created_at.isoformat() if proj.created_at else None,
        })

    return {"projects": result}


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a project and all associated files."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Clean up storage files
    storage_root = Path(settings.STORAGE_LOCAL_ROOT).resolve()
    for subdir in ["clips", "uploads", "transcripts"]:
        project_dir = storage_root / subdir / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)

    # Delete from DB (cascade will handle video, transcript, clips)
    db.delete(project)
    db.commit()

    logger.info(f"Admin deleted project {project_id}")
    return {"message": f"Project '{project.title}' deleted"}


# ══════════════════════════════════════════════════════════════════
# 6. SERVICE CONTROL (Restart)
# ══════════════════════════════════════════════════════════════════

@router.post("/restart/{service}")
def restart_service(
    service: str,
    admin: User = Depends(require_admin),
):
    """
    Restart a NexClip service.
    Supported: backend, celery, nex_agent, nexearch, arc_agent, all
    """
    global _restart_required

    if service not in _restartable_services():
        raise HTTPException(
            status_code=400,
            detail=f"Service must be one of: {', '.join(_restartable_services())}",
        )

    try:
        restarted_messages: List[str] = []
        if service == "all":
            for service_name in ("celery", "nex_agent", "arc_agent", "nexearch", "backend"):
                restarted_messages.append(_restart_single_service(service_name))
            logger.info("Admin restarted all managed services")
        else:
            restarted_messages.append(_restart_single_service(service))
            logger.info(f"Admin restarted service '{service}'")

        _restart_required = False
        return {
            "message": "; ".join(restarted_messages),
            "service": service,
            "restart_required": False,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restart failed: {e}")


# ══════════════════════════════════════════════════════════════════
# 7. LOGS
# ══════════════════════════════════════════════════════════════════

@router.get("/logs")
def get_error_logs(admin: User = Depends(require_admin)):
    """Read the recent Celery error log."""
    log_path = Path(__file__).resolve().parent.parent.parent / "celery_error.log"

    if not log_path.exists():
        return {"logs": "", "message": "No error log file found — no errors recorded yet."}

    try:
        content = log_path.read_text(encoding="utf-8")
        # Return last 5000 chars for display
        return {
            "logs": content[-5000:] if len(content) > 5000 else content,
            "total_size": len(content),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


@router.delete("/logs")
def clear_error_logs(admin: User = Depends(require_admin)):
    """Clear the Celery error log."""
    log_path = Path(__file__).resolve().parent.parent.parent / "celery_error.log"
    if log_path.exists():
        log_path.write_text("", encoding="utf-8")
    return {"message": "Error log cleared"}


# ══════════════════════════════════════════════════════════════════
# 8. NEXEARCH & AGENT SERVICE HEALTH
# ══════════════════════════════════════════════════════════════════

@router.get("/services/health")
def check_all_services(admin: User = Depends(require_admin)):
    """
    Check health of ALL NexClip services:
    Backend (self), Nex Agent (8001), Nexearch (8002), Arc Agent (8003), Redis, Celery
    """
    import httpx

    services = {}

    # Backend — always online if this endpoint is responding
    services["backend"] = {"status": "online", "port": 8000, "latency_ms": 0}

    # Check agent services in parallel to keep admin health responsive
    probe_targets = [
        ("nex_agent", 8001, "http://localhost:8001/health"),
        ("nexearch", 8002, "http://localhost:8002/health"),
        ("arc_agent", 8003, "http://localhost:8003/health"),
    ]
    with ThreadPoolExecutor(max_workers=len(probe_targets)) as executor:
        for svc_name, payload in executor.map(lambda args: _probe_http_service(*args), probe_targets):
            services[svc_name] = payload

    # Redis
    try:
        import redis
        t0 = time.time()
        r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        latency = int((time.time() - t0) * 1000)
        services["redis"] = {"status": "online", "latency_ms": latency}
    except Exception as e:
        services["redis"] = {"status": "offline", "error": str(e)[:100]}

    # Celery
    try:
        celery_processes = _find_service_processes("celery")
        if celery_processes:
            services["celery"] = {
                "status": "online",
                "workers": len(celery_processes),
                "active_tasks": len(celery_processes),
            }
        else:
            services["celery"] = {"status": "offline", "error": "No workers found"}
    except Exception as e:
        services["celery"] = {"status": "offline", "error": str(e)[:100]}

    return {"services": services}


# ══════════════════════════════════════════════════════════════════
# 9. CAPTION STYLES + PREVIEW INFO
# ══════════════════════════════════════════════════════════════════

@router.get("/caption-styles")
def list_caption_styles(admin: User = Depends(require_admin)):
    """List all 18 caption styles with their details."""
    try:
        from app.captions.style_registry import get_all_styles
        styles = get_all_styles()
        result = []
        for s in styles:
            ep = s.extra_params or {}
            result.append({
                "style_id": s.style_id,
                "display_name": s.display_name,
                "font_family": s.font_family,
                "font_weight": s.font_weight,
                "font_size": s.font_size,
                "position": s.position,
                "primary_color": s.primary_color,
                "active_color": ep.get("active_color", s.primary_color),
                "uppercase": s.uppercase,
                "letter_spacing": s.letter_spacing,
                "scale_active": s.scale_active,
            })
        return {"styles": result, "total": len(result)}
    except Exception as e:
        return {"styles": [], "total": 0, "error": str(e)}
