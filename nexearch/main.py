"""
Nexearch FastAPI application.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from nexearch.config import get_nexearch_settings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

settings = get_nexearch_settings()


def _directory_status(path: Path, *, label: str) -> dict:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "label": label, "path": str(path)}
    except Exception as exc:
        return {"ok": False, "label": label, "path": str(path), "error": str(exc)}


def _health_payload() -> dict:
    components = {
        "clients_dir": _directory_status(settings.clients_dir_path, label="clients"),
        "chroma_dir": _directory_status(settings.chroma_persist_path, label="chroma"),
        "arc_memory": _directory_status(settings.arc_memory_path, label="arc_memory"),
    }
    overall_ok = all(component["ok"] for component in components.values())
    return {
        "service": "nexearch",
        "version": "1.1.0",
        "env": settings.APP_ENV,
        "status": "ok" if overall_ok else "degraded",
        "has_secure_secret_key": settings.has_secure_secret_key,
        "components": components,
        "config": {
            "has_metricool": settings.has_metricool,
            "has_apify": settings.has_apify,
            "arc_agent_enabled": settings.ARC_AGENT_ENABLED,
            "nex_agent_enabled": settings.NEX_AGENT_ENABLED,
        },
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nexearch starting up")
    from nexearch.data.system_meta import SystemMeta
    from nexearch.data.universal_store import get_universal_store

    get_universal_store()
    SystemMeta()
    yield
    logger.info("Nexearch shutting down")


app = FastAPI(
    title="Nexearch",
    description="Self-evolving social media intelligence and publishing agent",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from nexearch.api.v1.analyze import router as pipeline_router
from nexearch.api.v1.arc_agent import router as arc_router
from nexearch.api.v1.clients import router as clients_router
from nexearch.api.v1.data_explorer import router as data_router
from nexearch.api.v1.directive import router as directive_router
from nexearch.api.v1.intelligence import router as intell_router

app.include_router(clients_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(directive_router, prefix="/api/v1")
app.include_router(data_router, prefix="/api/v1")
app.include_router(arc_router, prefix="/api/v1")
app.include_router(intell_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return _health_payload()


@app.get("/ready")
async def ready(response: Response):
    payload = _health_payload()
    ready_state = all(component["ok"] for component in payload["components"].values()) and (
        settings.has_secure_secret_key or settings.APP_ENV != "production"
    )
    payload["ready"] = ready_state
    if not ready_state:
        response.status_code = 503
    return payload


@app.get("/status")
async def system_status():
    from nexearch.data.system_meta import SystemMeta

    meta = SystemMeta()
    payload = _health_payload()
    payload.update(
        {
            "clients": meta.get_all_client_summaries(),
            "system": meta.get_system_status(),
            "capabilities": {
                "scraping_methods": ["apify", "platform_api", "crawlee_playwright", "buffer"],
                "publishing_methods": ["metricool", "platform_api", "crawlee_playwright", "buffer"],
                "platforms": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"],
                "evolution_modes": ["client_specific", "universal"],
            },
        }
    )
    return payload
