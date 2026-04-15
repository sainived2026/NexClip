"""
Nexearch — Analysis / Pipeline Routes
Trigger and monitor pipeline runs.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from loguru import logger
from nexearch.data.client_store import ClientDataStore

router = APIRouter(prefix="/pipeline", tags=["Nexearch Pipeline"])


def _status_payload(task_id: str, status: str, result: Any = None, info: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "info": info,
    }

    if isinstance(info, dict):
        payload["current_stage"] = info.get("stage")
        payload["progress"] = info.get("progress")
        payload["message"] = info.get("message")
        payload["scrape_total"] = info.get("scrape_total")
        payload["analysis_total"] = info.get("analysis_total")
        payload["scored_total"] = info.get("scored_total")
        payload["published_count"] = info.get("published_count")
        payload["errors"] = info.get("errors", [])
        return payload

    if isinstance(result, dict):
        payload["current_stage"] = result.get("status")
        payload["progress"] = 100 if status == "SUCCESS" else None
        payload["message"] = result.get("message")
        payload["scrape_total"] = result.get("scrape_total")
        payload["analysis_total"] = result.get("analysis_total")
        payload["scored_total"] = result.get("scored_total")
        payload["published_count"] = result.get("published_count")
        payload["errors"] = result.get("errors", [])
        return payload

    payload["current_stage"] = None
    payload["progress"] = None
    payload["message"] = None
    payload["scrape_total"] = None
    payload["analysis_total"] = None
    payload["scored_total"] = None
    payload["published_count"] = None
    payload["errors"] = []
    return payload


def _resolve_pipeline_context(config: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill account metadata from the client store when omitted by callers."""
    resolved = dict(config)
    client_id = (resolved.get("client_id") or "").strip()
    platform = (resolved.get("platform") or "").strip()

    if not client_id or not platform:
        return resolved

    try:
        store = ClientDataStore(client_id)
        manifest = store.get_manifest() or {}
        creds = store.get_credentials(platform)

        if not resolved.get("account_url"):
            resolved["account_url"] = creds.get("account_url", "")
        if not resolved.get("account_handle"):
            resolved["account_handle"] = manifest.get("account_handle", client_id)
        if not resolved.get("credentials"):
            resolved["credentials"] = creds
        if not resolved.get("platform_credentials"):
            resolved["platform_credentials"] = {platform: creds} if creds else {}
    except Exception as exc:
        logger.debug(f"Unable to resolve pipeline context from client store: {exc}")

    return resolved


@router.post("/run", summary="Trigger a pipeline run")
async def run_pipeline(config: Dict[str, Any]):
    """
    Trigger a full Nexearch pipeline run.

    Required fields:
    - client_id: str
    - account_url: str
    - platform: str (instagram|tiktok|youtube|linkedin|twitter|facebook)
    - account_handle: str

    Optional fields:
    - scraping_method: str (apify|platform_api|crawlee_playwright)
    - publishing_method: str (metricool|platform_api|crawlee_playwright)
    - credentials: dict
    - platform_credentials: dict of platform → creds
    - target_platforms: list of platforms to scrape
    - platform_accounts: dict of platform → account_url
    - max_posts: int (default 100)
    - skip_scrape: bool
    - skip_publish: bool
    - dry_run: bool
    - force_rescrape: bool
    - enable_universal_evolution: bool (default True)
    """
    config = _resolve_pipeline_context(config)

    required = ["client_id", "platform", "account_handle", "account_url"]
    for field in required:
        if not config.get(field):
            raise HTTPException(400, f"'{field}' is required")

    # Run via Celery if available, otherwise async
    try:
        from nexearch.tasks.pipeline import run_pipeline_task
        task = run_pipeline_task.delay(config)
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Pipeline queued for @{config['account_handle']} on {config['platform']}",
        }
    except Exception:
        # Fallback: run inline (for dev without Celery)
        from nexearch.agents.pipeline import run_nexearch_pipeline
        state = await run_nexearch_pipeline(**config)
        return {
            "pipeline_id": state.pipeline_id,
            "status": state.current_stage,
            "scrape_total": state.scrape_total,
            "analysis_total": state.analysis_total,
            "scored_total": len(state.scored_posts),
            "tier_distribution": state.tier_distribution,
            "directive_id": state.directive_id,
            "duration_seconds": state.total_duration_seconds,
            "errors": state.errors,
            "client_data_dir": state.client_data_dir,
            "nexclip_data_dir": state.nexclip_data_dir,
        }


@router.get("/status/{task_id}", summary="Get pipeline task status")
async def get_pipeline_status(task_id: str):
    """Check the status of a pipeline Celery task."""
    try:
        from nexearch.tasks.pipeline import celery_app
        from celery.backends.base import DisabledBackend

        if isinstance(celery_app.backend, DisabledBackend):
            return _status_payload(
                task_id=task_id,
                status="UNKNOWN",
                result=None,
                info={
                    "warning": "Celery result backend is disabled; live task status is unavailable for this Nexearch instance.",
                },
            )

        result = celery_app.AsyncResult(task_id)
        return _status_payload(
            task_id=task_id,
            status=result.status,
            result=result.result if result.ready() else None,
            info=result.info if not result.ready() else None,
        )
    except Exception as e:
        raise HTTPException(500, f"Cannot check task status: {e}")
