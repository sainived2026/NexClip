"""
NexClip FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
import redis
from sqlalchemy import text

from app.admin.routes import router as admin_router
from app.api.admin_check import router as admin_check_router
from app.api.auth import router as auth_router
from app.api.caption_preview_api import router as caption_preview_router
from app.api.captions_api import router as captions_router
from app.api.clips import router as clips_router
from app.api.projects import router as projects_router
from app.core.config import get_settings
from app.db.database import engine, init_db

settings = get_settings()

logger.remove()
logger.add(sys.stdout, serialize=True, level="DEBUG" if settings.APP_ENV == "development" else "INFO")


def _database_status() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"ok": True, "url": settings.DATABASE_URL, "kind": "sqlite" if settings.is_sqlite else "sql"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": settings.DATABASE_URL}


def _storage_status() -> dict:
    try:
        settings.storage_root_path.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "path": str(settings.storage_root_path)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(settings.storage_root_path)}


def _redis_status() -> dict:
    try:
        client = redis.from_url(settings.REDIS_URL, socket_timeout=1, socket_connect_timeout=1)
        client.ping()
        return {"ok": True, "url": settings.REDIS_URL}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": settings.REDIS_URL}


def _health_payload() -> dict:
    components = {
        "database": _database_status(),
        "storage": _storage_status(),
        "redis": _redis_status(),
    }
    overall_ok = all(components[name]["ok"] for name in ("database", "storage"))
    return {
        "app": settings.APP_NAME,
        "version": "2.1.0",
        "env": settings.APP_ENV,
        "status": "ok" if overall_ok else "degraded",
        "has_secure_secret_key": settings.has_secure_secret_key,
        "dev_auth_bypass_enabled": settings.ALLOW_DEV_AUTH_BYPASS,
        "components": components,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} ({settings.APP_ENV})")
    init_db()
    settings.storage_root_path.mkdir(parents=True, exist_ok=True)
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title="NexClip API",
    description="AI-powered video clipping engine",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage_path = Path(settings.STORAGE_LOCAL_ROOT)
storage_path.mkdir(parents=True, exist_ok=True)
app.mount("/static/storage", StaticFiles(directory=str(storage_path)), name="storage")

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(clips_router)
app.include_router(admin_router)
app.include_router(admin_check_router)
app.include_router(captions_router)
app.include_router(caption_preview_router)


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": "2.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return _health_payload()


@app.get("/ready")
def ready(response: Response):
    payload = _health_payload()
    ready_state = (
        payload["components"]["database"]["ok"]
        and payload["components"]["storage"]["ok"]
        and (payload["components"]["redis"]["ok"] or settings.APP_ENV == "development")
        and (settings.has_secure_secret_key or settings.APP_ENV != "production")
    )
    payload["ready"] = ready_state
    if not ready_state:
        response.status_code = 503
    return payload
