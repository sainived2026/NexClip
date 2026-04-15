"""
Nexearch — Data Explorer Routes
Access per-client and universal data directories.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from nexearch.data.client_store import ClientDataStore

router = APIRouter(prefix="/data", tags=["Nexearch Data Explorer"])


def _load_client_evolution_data(store, platform: str) -> Dict[str, Any]:
    """Load client evolution details for a platform from the file store."""
    evolution_dir = store.base_dir / "intelligence" / platform / "evolution"
    log_path = evolution_dir / "evolution_log.json"
    rubric_path = evolution_dir / "rubric_weights.json"

    log_data = {}
    rubric_data = {}

    if log_path.exists():
        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
    if rubric_path.exists():
        with open(rubric_path, "r", encoding="utf-8") as f:
            rubric_data = json.load(f)

    return {
        "platform": platform,
        "entries": log_data.get("entries", []) if isinstance(log_data, dict) else [],
        "rubric_weights": rubric_data.get("weights", {}) if isinstance(rubric_data, dict) else {},
        "history": rubric_data.get("history", []) if isinstance(rubric_data, dict) else [],
    }


@router.get("/{client_id}/manifest", summary="Get client manifest")
async def get_client_manifest(client_id: str):
    """Get the full client data manifest."""
    store = ClientDataStore(client_id)
    manifest = store.get_manifest()
    if not manifest:
        raise HTTPException(404, "Client not found")
    return manifest


@router.get("/{client_id}/nexclip/manifest", summary="Get NexClip manifest")
async def get_nexclip_manifest(client_id: str):
    """Get the NexClip enhancement manifest for a client."""
    from nexearch.data.nexclip_client_store import NexClipClientStore
    store = NexClipClientStore(client_id)
    return store.get_manifest()


@router.get("/{client_id}/nexclip/export", summary="Export NexClip config")
async def export_nexclip_config(client_id: str):
    """Export the full NexClip configuration for a client."""
    from nexearch.data.nexclip_client_store import NexClipClientStore
    store = NexClipClientStore(client_id)
    return store.export_nexclip_config()


@router.get("/{client_id}/scrapes/{platform}", summary="Get latest scrape")
async def get_latest_scrape(client_id: str, platform: str):
    """Get the most recent scrape data for a client on a specific platform."""
    store = ClientDataStore(client_id)
    data = store.get_latest_scrape(platform)
    if not data:
        return {"message": "No scrapes found", "client_id": client_id, "platform": platform}
    return data


@router.get("/{client_id}/dna/{platform}", summary="Get platform DNA")
async def get_platform_dna(client_id: str, platform: str):
    """Get the current Account DNA for a client on a specific platform."""
    store = ClientDataStore(client_id)
    dna = store.get_platform_dna(platform)
    if not dna:
        return {"message": "No DNA generated yet", "client_id": client_id, "platform": platform}
    return dna


@router.get("/{client_id}/evolution/{platform}", summary="Get client evolution data")
async def get_client_evolution(client_id: str, platform: str):
    """Get evolution log and rubric history for a client platform."""
    store = ClientDataStore(client_id)
    data = _load_client_evolution_data(store, platform)
    if not data["entries"] and not data["rubric_weights"]:
        return {
            "message": "No evolution data yet",
            "client_id": client_id,
            "platform": platform,
            "entries": [],
            "rubric_weights": {},
            "history": [],
        }
    data["client_id"] = client_id
    return data


@router.get("/universal/{platform}/patterns", summary="Get universal winning patterns")
async def get_universal_patterns(platform: str):
    """Get universal (cross-client) winning patterns for a platform."""
    from nexearch.data.universal_store import get_universal_store
    store = get_universal_store()
    return store.get_winning_patterns(platform)


@router.get("/universal/{platform}/dna", summary="Get universal DNA")
async def get_universal_dna(platform: str):
    """Get the universal DNA for a platform."""
    from nexearch.data.universal_store import get_universal_store
    store = get_universal_store()
    dna = store.get_universal_dna(platform)
    if not dna:
        return {"message": "No universal DNA yet", "platform": platform}
    return dna


@router.get("/universal/{platform}/benchmarks", summary="Get engagement benchmarks")
async def get_benchmarks(platform: str):
    """Get global engagement benchmarks for a platform."""
    from nexearch.data.universal_store import get_universal_store
    store = get_universal_store()
    return store.get_engagement_benchmarks(platform) or {"message": "No benchmarks yet"}


@router.get("/universal/trends", summary="Get global trends")
async def get_global_trends():
    """Get cross-platform global trends."""
    from nexearch.data.universal_store import get_universal_store
    store = get_universal_store()
    return store.get_global_trends() or {"message": "No trends data yet"}
