"""
Nexearch — Celery Pipeline Task
Background task for running the full Nexearch pipeline.
Uses NexClip's existing Celery application.
"""

import asyncio
from typing import Dict, Any, Optional
from loguru import logger

# Import NexClip's Celery app
try:
    from app.workers.celery_app import celery_app
except ImportError:
    # Fallback when running outside NexClip context
    from celery import Celery
    celery_app = Celery("nexearch")
    celery_app.config_from_object({
        "broker_url": "redis://localhost:6379/0",
        "result_backend": "redis://localhost:6379/0",
        "task_track_started": True,
        "result_expires": 3600,
    })


def _resolve_pipeline_config(pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill account metadata from client storage for worker-triggered jobs."""
    resolved = dict(pipeline_config)
    client_id = (resolved.get("client_id") or "").strip()
    platform = (resolved.get("platform") or "").strip()

    if not client_id or not platform:
        return resolved

    try:
        from nexearch.data.client_store import ClientDataStore

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
        logger.debug(f"Unable to resolve worker pipeline config from client store: {exc}")

    return resolved


def _count_evolution_entries(state: Any) -> int:
    """Count evolution outputs whether they were stored flat or per-platform."""
    return len(getattr(state, "evolution_changes", None) or getattr(state, "platform_evolution", None) or {})


@celery_app.task(
    name="nexearch.pipeline.run",
    queue="nexearch",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=3600,      # 1 hour soft limit
    time_limit=4200,           # 1 hour 10 min hard limit
)
def run_pipeline_task(self, pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to run the Nexearch pipeline in the background.

    Args:
        pipeline_config: {
            "client_id": str,
            "account_url": str,
            "platform": str,
            "account_handle": str,
            "scraping_method": "apify|platform_api|crawlee_playwright",
            "publishing_method": "metricool|platform_api|crawlee_playwright",
            "credentials": {},
            "platform_credentials": {},
            "target_platforms": [],
            "platform_accounts": {},
            "max_posts": 100,
            "skip_scrape": False,
            "skip_publish": False,
            "dry_run": False,
            "force_rescrape": False,
            "enable_universal_evolution": True,
        }
    """
    task_id = self.request.id
    logger.info(f"[Celery] Pipeline task {task_id} started for "
               f"client {pipeline_config.get('client_id')}")
    pipeline_config = _resolve_pipeline_config(pipeline_config)

    # Update task state
    self.update_state(state="PROGRESS", meta={"progress": 0, "stage": "init"})

    def progress_callback(data):
        self.update_state(state="PROGRESS", meta=data)

    try:
        from nexearch.agents.pipeline import NexearchPipeline
        pipeline = NexearchPipeline(progress_callback=progress_callback)

        # Run async pipeline in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            state = loop.run_until_complete(pipeline.run(**pipeline_config))
        finally:
            loop.close()

        result = {
            "pipeline_id": state.pipeline_id,
            "status": state.current_stage,
            "scrape_total": state.scrape_total,
            "analysis_total": state.analysis_total,
            "scored_total": len(state.scored_posts),
            "tier_distribution": state.tier_distribution,
            "evolution_changes": _count_evolution_entries(state),
            "directive_id": state.directive_id,
            "published_count": len(state.published_posts),
            "duration_seconds": state.total_duration_seconds,
            "errors": state.errors,
            "client_data_dir": state.client_data_dir,
            "nexclip_data_dir": state.nexclip_data_dir,
        }

        logger.info(f"[Celery] Pipeline task {task_id} completed: {result['status']}")
        return result

    except Exception as e:
        logger.error(f"[Celery] Pipeline task {task_id} failed: {e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(
    name="nexearch.pipeline.rescrape",
    queue="nexearch",
    bind=True,
    max_retries=1,
    soft_time_limit=1800,
)
def rescrape_task(self, client_id: str, platform: str,
                  credentials: Dict = None) -> Dict[str, Any]:
    """Periodic re-scrape task for refreshing metrics."""
    logger.info(f"[Celery] Rescrape task for client {client_id} on {platform}")

    config = _resolve_pipeline_config({
        "client_id": client_id,
        "platform": platform,
        "credentials": credentials or {},
        "skip_publish": True,  # Rescrape = analysis-only
        "force_rescrape": True,
    })

    try:
        from nexearch.agents.pipeline import NexearchPipeline
        pipeline = NexearchPipeline()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            state = loop.run_until_complete(pipeline.run(**config))
        finally:
            loop.close()

        return {
            "status": state.current_stage,
            "client_id": client_id,
            "platform": platform,
            "scrape_total": state.scrape_total,
            "errors": state.errors,
        }
    except Exception as e:
        return {"status": "error", "client_id": client_id, "platform": platform, "error": str(e)}


@celery_app.task(
    name="nexearch.pipeline.performance_poll",
    queue="nexearch",
    bind=True,
    soft_time_limit=300,
)
def performance_poll_task(self, client_id: str, post_id: str,
                           poll_window: str) -> Dict[str, Any]:
    """Poll performance metrics for a published post at a specific window."""
    from nexearch.data.client_store import ClientDataStore

    logger.info(f"[Celery] Performance poll for {post_id} at {poll_window}")

    # TODO: Implement Metricool performance polling
    # For now, save placeholder
    try:
        store = ClientDataStore(client_id)
        store.save_performance("unknown", post_id, poll_window, {
            "poll_window": poll_window, "status": "pending_implementation",
        })
        return {"status": "polled", "post_id": post_id, "window": poll_window}
    except Exception as e:
        return {"status": "error", "error": str(e)}
