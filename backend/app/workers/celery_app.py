"""
NexClip — Celery application & configuration.
Production-ready: 3 dedicated queues for 750+ simultaneous tasks.
"""
import os
import sys
from pathlib import Path

# ── 🚨 CRITICAL WINDOWS FIX FOR CTRANSLATE2 / WHISPER 🚨 ──
# faster-whisper (CTranslate2) relies on Intel OpenMP (libiomp5md.dll).
# When run inside a multi-threaded Python environment like Celery on Windows,
# it attempts to initialize OpenMP multiple times, triggering a silent Access Violation (0xC0000005)
# that instantly kills the python.exe process without any errors.
# These environment variables FORCE it to ignore the collision and restrict its thread spawning.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["CTRANSLATE2_OMP_NUM_THREADS"] = "1"


def _ensure_worker_import_paths() -> None:
    """
    Celery is commonly launched with cwd=backend while the Nexearch package
    lives at the repository root. Make both import roots explicit so startup
    works from terminals, admin restarts, and detached processes.
    """
    backend_root = Path(__file__).resolve().parents[2]
    repo_root = backend_root.parent
    for path in (str(repo_root), str(backend_root)):
        if path not in sys.path:
            sys.path.insert(0, path)


_ensure_worker_import_paths()

from celery import Celery
from app.core.config import get_settings
import app.core.binaries  # noqa: F401 — ensures ffmpeg/yt-dlp are on PATH

settings = get_settings()

celery_app = Celery(
    "nexclip",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.tasks",
        "app.workers.caption_tasks",
        "nexearch.tasks.pipeline",
    ],
)

celery_app.conf.update(
    # ── Serialization ──
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # ── Task Behavior ──
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # ── Timeouts ──
    task_soft_time_limit=7200,    # 2 hour soft limit (long videos need time)
    task_time_limit=10800,        # 3 hour hard limit
    task_default_retry_delay=60,
    task_max_retries=3,

    # ── Worker Pool ──
    # 'threads' pool: CPU-heavy work runs as subprocesses (FFmpeg, MediaPipe C++)
    # which bypass the GIL. API calls (ElevenLabs, LLM) are pure I/O.
    worker_pool="threads",

    # ── Queue Routing ──
    # Each task type goes to its own queue so dedicated workers can process them
    # independently. This means video processing, captioning, and Nexearch
    # NEVER compete for the same worker slots.
    #
    # Production: launch 3 workers, each consuming its own queue:
    #   celery worker -Q video     --concurrency=100
    #   celery worker -Q captions  --concurrency=600
    #   celery worker -Q nexearch  --concurrency=50
    #
    task_routes={
        "nexclip.process_video":              {"queue": "video"},
        "captions.apply_style":               {"queue": "captions"},
        "nexearch.pipeline.run":              {"queue": "nexearch"},
        "nexearch.pipeline.rescrape":         {"queue": "nexearch"},
        "nexearch.pipeline.performance_poll": {"queue": "nexearch"},
    },
    # Fallback: any un-routed task goes to the default 'celery' queue
    task_default_queue="celery",

    # ── Memory Management ──
    # NOTE: worker_max_memory_per_child and worker_max_tasks_per_child
    # only work with the 'prefork' pool, NOT 'threads'. They were causing
    # silent worker kills during GPU-heavy Whisper transcription.
    # Removed to prevent the pipeline from dying mid-execution.
)


from celery.signals import worker_ready
from loguru import logger

@worker_ready.connect
def handle_worker_ready(**kwargs):
    """
    Auto-Resume stuck projects on Celery worker startup.
    If the worker crashed or was killed, projects will be left in 
    TRANSCRIBING/ANALYZING/GENERATING_CLIPS status.
    """
    logger.info("Celery Worker Ready: Scanning for stuck projects to auto-resume...")
    try:
        from app.db.database import SessionLocal
        from app.db.models import Project, ProjectStatus
        from app.workers.tasks import process_video_task

        db = SessionLocal()
        stuck_statuses = [
            ProjectStatus.TRANSCRIBING,
            ProjectStatus.ANALYZING,
            ProjectStatus.GENERATING_CLIPS,
            ProjectStatus.UPLOADED
        ]
        
        stuck_projects = db.query(Project).filter(Project.status.in_(stuck_statuses)).all()
        if not stuck_projects:
            logger.info("No stuck projects found. All good.")
        else:
            logger.warning(f"Found {len(stuck_projects)} stuck projects. Re-queueing for resume...")
            for proj in stuck_projects:
                logger.info(f"Auto-resuming project {proj.id} (Status: {proj.status})")
                process_video_task.delay(proj.id)
                
        db.close()
    except Exception as e:
        logger.error(f"Failed to auto-resume projects: {e}")
