"""
Nexearch — ClipDirective Routes
Serve and override ClipDirectives + NexClip system prompt injections.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, List
from loguru import logger

router = APIRouter(prefix="/directive", tags=["Nexearch Directives"])


@router.get("/{client_id}/{platform}", summary="Get active directive")
async def get_active_directive(client_id: str, platform: str):
    """Get the active ClipDirective for a client + platform combination."""
    from nexearch.data.client_store import ClientDataStore
    store = ClientDataStore(client_id)

    # Get active directive from data store
    directive_path = store.base_dir / "directives" / platform / "active_directive.json"
    if directive_path.exists():
        import json
        with open(directive_path) as f:
            return json.load(f)

    raise HTTPException(404, f"No active directive for {client_id} on {platform}")


@router.get("/{client_id}/{platform}/injection", summary="Get NexClip system prompt injection")
async def get_nexclip_injection(client_id: str, platform: str):
    """Get the NexClip system prompt injection string for this client."""
    from nexearch.data.nexclip_client_store import NexClipClientStore
    store = NexClipClientStore(client_id)
    active = store.get_active_prompt()

    if active:
        return {"client_id": client_id, "platform": platform,
                "prompt": active.get("prompt", ""),
                "injected_at": active.get("injected_at", "")}

    return {"client_id": client_id, "platform": platform, "prompt": "",
            "message": "No active injection"}


@router.post("/{client_id}/{platform}/override", summary="Override directive")
async def override_directive(client_id: str, platform: str,
                              override: Dict[str, Any]):
    """Override specific directive parameters for a client + platform."""
    from nexearch.data.client_store import ClientDataStore
    import json, uuid

    store = ClientDataStore(client_id)

    # Load current directive
    directive_path = store.base_dir / "directives" / platform / "active_directive.json"
    if not directive_path.exists():
        raise HTTPException(404, "No active directive to override")

    with open(directive_path) as f:
        current = json.load(f)

    # Merge overrides
    directive = current.get("directive", {})
    for key, value in override.items():
        if isinstance(value, dict) and key in directive:
            directive[key].update(value)
        else:
            directive[key] = value

    # Save as new directive
    override_id = str(uuid.uuid4())[:8]
    store.save_directive(platform, f"override_{override_id}", directive)

    return {"status": "overridden", "override_id": override_id,
            "platform": platform, "client_id": client_id}


@router.get("/{client_id}/writing/{platform}", summary="Get writing profile")
async def get_writing_profile(client_id: str, platform: str):
    """Get the writing profile for a client + platform."""
    from nexearch.data.nexclip_client_store import NexClipClientStore
    store = NexClipClientStore(client_id)
    profile = store.get_writing_profile(platform)
    if profile:
        return profile
    return {"platform": platform, "profile": {}, "message": "No writing profile yet"}
