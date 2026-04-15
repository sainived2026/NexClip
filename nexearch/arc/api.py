"""
Arc Agent — REST API Routes
================================
REST endpoints for Arc Agent interactions.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["Arc Agent"])


# ── Request/Response Models ─────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = ""
    client_id: str = ""

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    tool_calls: int = 0


def _collect_chat_stream_result(agent, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Collect streamed Arc Agent output into a sync JSON response."""
    from nex_agent.response_validator import ResponseValidator

    response_parts = []
    tool_calls = []
    errors = []

    for chunk in agent.chat_stream(message, context=context):
        try:
            parsed = json.loads(chunk) if isinstance(chunk, str) else chunk
        except (TypeError, json.JSONDecodeError):
            response_parts.append(str(chunk))
            continue

        event_type = parsed.get("type", "token")
        if event_type == "token":
            response_parts.append(parsed.get("content", ""))
        elif event_type == "tool_call":
            if parsed.get("status") == "complete":
                tool_calls.append({
                    "name": parsed.get("name", ""),
                    "arguments": parsed.get("arguments", {}),
                    "result": parsed.get("result"),
                })
        elif event_type == "error":
            errors.append(parsed.get("content", "Unknown error"))

    raw_response = "".join(response_parts).strip()
    _, response_text = ResponseValidator().sanitize_chat_response(raw_response)
    if not response_text and errors:
        response_text = errors[-1]

    return {
        "response": response_text,
        "tool_calls": tool_calls,
        "errors": errors,
    }


# ── Chat endpoints ──────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to Arc Agent and get a response."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()

    context = {}
    if request.client_id:
        try:
            from nexearch.data.client_store import ClientDataStore
            store = ClientDataStore(request.client_id)
            context["client_context"] = store.get_client_summary()
        except Exception:
            pass

    conv_id = request.conversation_id or str(uuid.uuid4())
    sm = agent.streaming_manager
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

    if sm:
        try:
            sm.create_conversation(conv_id, "admin")
        except Exception:
            pass

        try:
            sm.save_user_message(user_msg_id, conv_id, "admin", request.message)
            sm.create_stream(assistant_msg_id, conv_id, "admin")
        except Exception:
            pass

    collected = _collect_chat_stream_result(agent, request.message, context=context)

    if sm:
        try:
            if collected["response"]:
                sm.append_tokens(assistant_msg_id, collected["response"])
            sm.finalize_stream(
                assistant_msg_id,
                tool_calls=collected["tool_calls"] if collected["tool_calls"] else None,
                error=collected["errors"][-1] if collected["errors"] else None,
            )
        except Exception:
            pass

    return ChatResponse(
        response=collected["response"],
        conversation_id=conv_id,
        tool_calls=len(collected["tool_calls"]),
    )


@router.get("/chat/stream")
async def chat_stream_sse(
    message: str = Query(...),
    conversation_id: str = Query(default=""),
    client_id: str = Query(default=""),
):
    """SSE streaming chat endpoint."""
    from fastapi.responses import StreamingResponse
    from nexearch.arc.core import get_arc_agent

    agent = get_arc_agent()
    context = {}
    if client_id:
        try:
            from nexearch.data.client_store import ClientDataStore
            store = ClientDataStore(client_id)
            context["client_context"] = store.get_client_summary()
        except Exception:
            pass

    def event_generator():
        for chunk in agent.chat_stream(message, context=context):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# ── Status endpoints ────────────────────────────────────────

@router.get("/status")
async def status():
    """Get Arc Agent status."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    return agent.get_status()


@router.get("/history")
async def history(limit: int = Query(default=50)):
    """Get conversation history."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    return {"history": agent.get_history(limit)}


@router.post("/history/clear")
async def clear_history():
    """Clear conversation history."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    agent.clear_history()
    return {"cleared": True}


# ── Tool endpoints ──────────────────────────────────────────

@router.get("/tools")
async def list_tools():
    """List all Arc Agent tools."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.tool_executor:
        return {"tools": []}
    return {
        "tools": agent.tool_executor.get_all_tools(),
        "count": agent.tool_executor.get_tool_count(),
        "categories": agent.tool_executor.get_tool_categories(),
    }


@router.post("/tools/execute")
async def execute_tool(tool_name: str, arguments: Dict[str, Any] = {}):
    """Execute an Arc Agent tool directly."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.tool_executor:
        raise HTTPException(500, "Tool executor not initialized")
    result = agent.tool_executor.execute(tool_name, arguments)
    return {"tool": tool_name, "result": result}


@router.get("/tools/search")
async def search_tools(query: str):
    """Search tools by name or description."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.tool_executor:
        return {"tools": []}
    return {"tools": agent.tool_executor.search_tools(query)}


# ── Sub-agent endpoints ─────────────────────────────────────

@router.get("/sub-agents")
async def list_sub_agents():
    """List all sub-agents."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.sub_agent_registry:
        return {"agents": []}
    return {"agents": agent.sub_agent_registry.get_all_agents()}


@router.get("/sub-agents/tasks")
async def sub_agent_tasks(limit: int = Query(default=20)):
    """Get sub-agent task history."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.sub_agent_registry:
        return {"history": []}
    return {"history": agent.sub_agent_registry.get_task_history(limit)}


# ── Memory endpoints ────────────────────────────────────────

@router.get("/memory/sessions")
async def memory_sessions(limit: int = Query(default=20)):
    """Get recent memory sessions."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.memory:
        return {"sessions": []}
    return {"sessions": agent.memory.get_session_list(limit)}


@router.get("/memory/decisions")
async def memory_decisions(limit: int = Query(default=10)):
    """Get recent decisions."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.memory:
        return {"decisions": []}
    return {"decisions": agent.memory.get_recent_decisions(limit)}


@router.get("/memory/pipeline-runs")
async def memory_pipeline_runs(limit: int = Query(default=20)):
    """Get recent pipeline runs."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.memory:
        return {"runs": []}
    return {"runs": agent.memory.get_recent_pipeline_runs(limit)}


@router.get("/memory/alerts")
async def memory_alerts():
    """Get active alerts."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if not agent.memory:
        return {"alerts": []}
    return {"alerts": agent.memory.get_active_alerts()}


# ── Conversation management (mirrors Nex Agent) ────────────

@router.get("/conversations")
async def list_conversations():
    """List all Arc Agent conversations."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if agent.streaming_manager:
        try:
            convs = agent.streaming_manager.list_conversations()
            return {"conversations": convs}
        except Exception:
            pass
    return {"conversations": []}


@router.post("/conversations")
async def create_conversation():
    """Create a new conversation."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    conv_id = str(uuid.uuid4())
    if agent.streaming_manager:
        try:
            agent.streaming_manager.create_conversation(conv_id, "admin")
        except Exception:
            pass
    return {"id": conv_id, "title": "New Chat", "created_at": "", "updated_at": "", "message_count": 0}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """Get messages for a conversation."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if agent.streaming_manager:
        try:
            msgs = agent.streaming_manager.get_conversation_messages(conversation_id)
            return {"messages": msgs}
        except Exception:
            pass
    return {"messages": []}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    if agent.streaming_manager:
        try:
            agent.streaming_manager.delete_conversation(conversation_id)
        except Exception:
            pass
    return {"deleted": True}


# ── Model info ──────────────────────────────────────────────

@router.get("/model")
async def model_info():
    """Get active model information."""
    from nexearch.arc.core import get_arc_agent
    agent = get_arc_agent()
    model = "gemini-3.1-flash-lite-preview"
    try:
        if hasattr(agent, "llm") and hasattr(agent.llm, "model_name"):
            model = agent.llm.model_name
    except Exception:
        pass
    return {"active_model": model}


# ══════════════════════════════════════════════════════════════
# CLIENT MANAGEMENT (Frontend CRUD)
# ══════════════════════════════════════════════════════════════

@router.get("/clients")
async def list_clients_proxy():
    """List all Nexearch clients with capabilities."""
    from nexearch.data.system_meta import SystemMeta
    from nexearch.data.client_store import ClientDataStore
    meta = SystemMeta()
    clients = meta.get_all_client_summaries()

    enriched = []
    for c in clients:
        cid = c.get("client_id", "")
        try:
            store = ClientDataStore(cid)
            caps = store.get_all_capabilities()
            c["capabilities"] = caps.get("summary", {})
            c["platform_details"] = caps.get("platforms", {})
        except Exception:
            c["capabilities"] = {}
            c["platform_details"] = {}
        enriched.append(c)

    return {"clients": enriched}


@router.post("/clients")
async def create_client_proxy(data: Dict[str, Any]):
    """
    Create a client with full credential management.

    Expected payload:
    {
        "name": "Clip Aura",
        "platforms": {
            "instagram": {
                "account_url": "https://instagram.com/clip_aura",
                "metricool_api_key": "abc123"
            }
        }
    }
    """
    import json as _json
    from pathlib import Path
    from datetime import datetime, timezone

    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Client name is required")

    client_id = data.get("client_id", name.lower().replace(" ", "_").replace("-", "_"))
    platforms_input = data.get("platforms", {})

    # Validate: at least 1 platform must provide real credentials
    platform_list = []
    if isinstance(platforms_input, dict):
        platform_list = [p for p, creds in platforms_input.items()
                         if isinstance(creds, dict) and any(v for v in creds.values() if v)]
    elif isinstance(platforms_input, list):
        platform_list = platforms_input

    if not platform_list:
        raise HTTPException(400, "At least 1 platform with at least a page link or API key is required")

    # Create NexClip client directory
    project_root = Path(__file__).resolve().parent.parent.parent
    nexclip_dir = project_root / "clients" / client_id
    nexclip_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "client_id": client_id,
        "name": name,
        "platforms": platform_list,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (nexclip_dir / "config.json").write_text(_json.dumps(config, indent=2))
    (nexclip_dir / "history.json").write_text("[]")

    # Create Nexearch client data directory + save credentials
    from nexearch.data.client_store import ClientDataStore
    client_store = ClientDataStore(client_id, name)

    if isinstance(platforms_input, dict):
        for platform, creds in platforms_input.items():
            if isinstance(creds, dict) and any(v for v in creds.values() if v):
                client_store.save_credentials(platform, creds)

    caps = client_store.get_all_capabilities()

    return {
        "client_id": client_id,
        "name": name,
        "platforms": platform_list,
        "capabilities": caps.get("summary", {}),
        "status": "created",
    }


@router.put("/clients/{client_id}")
async def update_client_proxy(client_id: str, data: Dict[str, Any]):
    """
    Update credentials for an existing client, or add a new platform.

    Payload:
    {
        "platform": "instagram",         // existing platform to update
        "credentials": { ... },          // new/updated credentials
        "name": "New Name",              // optional rename
        "add_platform": "tiktok",        // optional new platform
        "add_credentials": { ... }       // credentials for new platform
    }
    """
    import json as _json
    from pathlib import Path
    from nexearch.data.client_store import ClientDataStore

    project_root = Path(__file__).resolve().parent.parent.parent
    nexclip_config = project_root / "clients" / client_id / "config.json"
    nex_data = project_root / "nexearch_data" / "clients" / client_id

    if not nexclip_config.exists() and not nex_data.exists():
        raise HTTPException(404, f"Client '{client_id}' not found")

    store = ClientDataStore(client_id)

    # Rename if requested
    new_name = data.get("name", "").strip()
    if new_name and nexclip_config.exists():
        cfg = _json.loads(nexclip_config.read_text(encoding="utf-8"))
        cfg["name"] = new_name
        nexclip_config.write_text(_json.dumps(cfg, indent=2), encoding="utf-8")

    # Update an existing platform's credentials
    platform = data.get("platform", "").strip().lower()
    credentials = data.get("credentials", {})
    if platform and credentials:
        store.save_credentials(platform, credentials)

    # Add a brand-new platform
    add_platform = data.get("add_platform", "").strip().lower()
    add_creds = data.get("add_credentials", {})
    if add_platform and add_creds:
        store.save_credentials(add_platform, add_creds)
        if nexclip_config.exists():
            cfg = _json.loads(nexclip_config.read_text(encoding="utf-8"))
            if add_platform not in cfg.get("platforms", []):
                cfg.setdefault("platforms", []).append(add_platform)
            nexclip_config.write_text(_json.dumps(cfg, indent=2), encoding="utf-8")

    caps = store.get_all_capabilities()
    return {
        "client_id": client_id,
        "status": "updated",
        "capabilities": caps.get("summary", {}),
    }


@router.post("/clients/{client_id}/verify")
async def verify_client_credentials_endpoint(client_id: str, data: Dict[str, Any] = None):
    """
    Verify that stored credentials actually match their account URLs.

    Optional payload:
    {
        "platform": "instagram",    // verify only this platform
        "credentials": { ... }      // test these creds (not yet saved)
    }

    Returns per-method verification per platform:
    {
        "client_id": "...",
        "results": {
            "instagram": {
                "overall_verified": true,
                "verifications": {
                    "metricool":    {"verified": true,  "message": "..."},
                    "page_link":    {"verified": true,  "message": "..."},
                    "login":        {"verified": false, "error":   "..."}
                }
            }
        }
    }
    """
    from nexearch.data.client_store import ClientDataStore
    from nexearch.services.credential_verifier import verify_client_platform

    store = ClientDataStore(client_id)
    caps = store.get_all_capabilities()
    all_platforms = list((caps.get("platforms") or {}).keys())

    payload = data or {}
    single_platform = payload.get("platform", "").strip().lower()
    override_creds = payload.get("credentials")

    target_platforms = [single_platform] if single_platform else all_platforms

    results = {}
    for plat in target_platforms:
        creds = override_creds if override_creds else (store.get_credentials(plat) or {})
        try:
            result = await verify_client_platform(client_id, plat, creds)
            results[plat] = result
        except Exception as exc:
            results[plat] = {
                "client_id": client_id,
                "platform": plat,
                "overall_verified": False,
                "overall_error_summary": str(exc),
                "verifications": {},
            }

    return {"client_id": client_id, "results": results}


@router.delete("/clients/{client_id}")
async def delete_client_proxy(client_id: str):
    """Delete a client permanently from both NexClip and Nexearch stores."""
    import shutil
    import logging
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent

    nexclip_dir = project_root / "clients" / client_id
    if nexclip_dir.exists():
        try:
            shutil.rmtree(nexclip_dir)
        except Exception as e:
            logging.error(f"Failed to delete NexClip directory {nexclip_dir}: {e}")

    nexearch_data_dir = project_root / "nexearch_data" / "clients" / client_id
    if nexearch_data_dir.exists():
        try:
            shutil.rmtree(nexearch_data_dir)
        except Exception as e:
            logging.error(f"Failed to delete Nexearch Data directory {nexearch_data_dir}: {e}")

    from nexearch.data.system_meta import SystemMeta
    meta = SystemMeta()
    meta.remove_client(client_id)

    return {"deleted": True, "client_id": client_id}


# ── DNA Viewer Endpoint ─────────────────────────────────────────────────────
@router.get("/clients/{client_id}/dna")
async def get_client_dna(client_id: str, platform: str = Query(default="")):
    """
    Return the Account DNA for a client.
    If platform is specified, returns only that platform's DNA.
    Otherwise returns DNA for every platform the client has intelligence on.
    """
    from nexearch.data.client_store import ClientDataStore
    from nexearch.data.system_meta import SystemMeta

    meta = SystemMeta()
    all_clients = meta.get_all_client_summaries()
    client_info = next((c for c in all_clients if c.get("client_id") == client_id), None)
    if not client_info:
        raise HTTPException(404, f"Client '{client_id}' not found")

    store = ClientDataStore(client_id, client_info.get("name", client_id))

    PLATFORMS_ALL = ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"]
    platforms_to_check = [platform] if platform else PLATFORMS_ALL

    dna_results: Dict[str, Any] = {}
    for plat in platforms_to_check:
        dna_data = store.get_platform_dna(plat)
        if dna_data:
            tier_data = store.get_latest_scores(plat) if hasattr(store, "get_latest_scores") else {}
            dna_results[plat] = {
                "version": dna_data.get("version", 1),
                "updated_at": dna_data.get("created_at", ""),
                "dna": dna_data.get("dna", dna_data),
                "tier_distribution": tier_data.get("tier_distribution", {}) if isinstance(tier_data, dict) else {},
            }

    return {
        "client_id": client_id,
        "client_name": client_info.get("name", client_id),
        "platforms_with_dna": list(dna_results.keys()),
        "dna": dna_results,
    }


@router.put("/clients/{client_id}/dna/{platform}")
async def update_client_dna(client_id: str, platform: str, payload: Dict[str, Any]):
    """
    Directly update/modify the Account DNA for a specific client platform.
    Used for manual overrides by users with precautions.
    """
    from nexearch.data.client_store import ClientDataStore
    
    store = ClientDataStore(client_id)
    # The payload contains the raw JSON string or parsed dict to replace the dna structure
    
    try:
        updated_dna = payload.get("dna", payload)
        
        # We need to save this back to clients/{client_id}/{platform}_dna.json
        import json
        dna_file = store.base_dir / f"{platform}_dna.json"
        
        current_data = {}
        if dna_file.exists():
            current_data = json.loads(dna_file.read_text(encoding="utf-8"))
            
        current_data["dna"] = updated_dna
        current_data["version"] = current_data.get("version", 1) + 1
        
        from datetime import datetime
        current_data["updated_at"] = datetime.utcnow().isoformat()
        
        dna_file.write_text(json.dumps(current_data, indent=2), encoding="utf-8")
        
        # Log this manual override as an evolution event as well so it's tracked
        store.log_evolution(
            platform=platform,
            cycle_id=f"manual-override-{int(datetime.utcnow().timestamp())}",
            change_summary="User manually modified DNA via intelligence dashboard.",
            patterns_added=["manual_override"],
            patterns_removed=[]
        )
        
        return {"success": True, "message": "DNA successfully modified."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
