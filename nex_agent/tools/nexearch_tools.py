"""
Nex Agent — Nexearch Integration Tools (Rewritten with Real Bridge)
=====================================================================
10 tools giving Nex Agent full control over Nexearch and Arc Agent
via the HTTP communication bridge.
"""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor


# ── Tool Implementations ───────────────────────────────────

def nexearch_system_status(**kwargs) -> Dict[str, Any]:
    """Get Nexearch system status (health, clients, pipeline runs)."""
    import httpx
    results = {}

    # Nexearch engine health
    try:
        r = httpx.get("http://localhost:8002/health", timeout=5)
        results["nexearch"] = r.json()
    except Exception as e:
        results["nexearch"] = {"status": "unreachable", "error": str(e)}

    # Arc Agent health
    try:
        r = httpx.get("http://localhost:8003/health", timeout=5)
        results["arc_agent"] = r.json()
    except Exception as e:
        results["arc_agent"] = {"status": "unreachable", "error": str(e)}

    return results


def nexearch_client_data(client_id: str, **kwargs) -> Dict[str, Any]:
    """Get all data for a specific Nexearch client."""
    try:
        from nexearch.data.client_store import ClientDataStore
        store = ClientDataStore(client_id)
        return store.get_client_summary()
    except Exception as e:
        return {"error": str(e)}


def nexearch_client_dna(client_id: str, platform: str, **kwargs) -> Dict[str, Any]:
    """Get Account DNA for a client on a specific platform."""
    try:
        from nexearch.data.client_store import ClientDataStore
        store = ClientDataStore(client_id)
        return store.get_platform_dna(platform) or {"message": "No DNA generated yet"}
    except Exception as e:
        return {"error": str(e)}


def nexearch_nexclip_enhancements(client_id: str, **kwargs) -> Dict[str, Any]:
    """Get NexClip enhancement tracking for a client."""
    try:
        from nexearch.data.nexclip_client_store import NexClipClientStore
        store = NexClipClientStore(client_id)
        return store.generate_enhancement_report()
    except Exception as e:
        return {"error": str(e)}


def nexearch_universal_patterns(platform: str = "all", **kwargs) -> Dict[str, Any]:
    """Get universal winning patterns across all clients."""
    try:
        from nexearch.data.universal_store import get_universal_store
        store = get_universal_store()
        return store.get_winning_patterns(platform)
    except Exception as e:
        return {"error": str(e)}


def nexearch_trigger_pipeline(client_id: str, platform: str,
                                account_handle: str = "",
                                dry_run: bool = True, **kwargs) -> Dict[str, Any]:
    """Trigger a full Nexearch pipeline via Celery."""
    try:
        from nexearch.tasks.pipeline import run_pipeline_task
        task = run_pipeline_task.delay({
            "client_id": client_id,
            "platform": platform,
            "account_handle": account_handle,
            "dry_run": dry_run,
        })
        return {"task_id": task.id, "status": "queued", "client_id": client_id}
    except Exception as e:
        return {"error": str(e), "hint": "Is Celery running?"}


def nexearch_change_history(client_id: str,
                              change_type: str = "all", **kwargs) -> Dict[str, Any]:
    """Get change audit trail for a client."""
    try:
        from nexearch.data.change_tracker import ChangeTracker
        tracker = ChangeTracker(client_id)
        return {"changes": tracker.get_history(change_type=change_type)}
    except Exception as e:
        return {"error": str(e)}


def nexearch_revert_change(client_id: str, change_id: str,
                             reason: str = "", **kwargs) -> Dict[str, Any]:
    """Revert a change (sends negative feedback to evolution engine)."""
    try:
        from nexearch.data.change_tracker import ChangeTracker
        tracker = ChangeTracker(client_id)
        return tracker.revert_change(change_id, reason=reason)
    except Exception as e:
        return {"error": str(e)}


def nexearch_chat_with_arc(message: str, client_id: str = "", **kwargs) -> Dict[str, Any]:
    """Chat with Arc Agent (Nexearch's controller). Full bidirectional communication."""
    # Log outgoing message to AgentBus
    try:
        from nex_agent.agent_bus import get_agent_bus
        bus = get_agent_bus()
        bus.nex_to_arc(message[:300], msg_type="chat")
    except Exception:
        pass

    try:
        from nexearch.bridge import get_arc_bridge
        bridge = get_arc_bridge()
        result = bridge.chat(message, client_id=client_id)

        # Log response to AgentBus
        try:
            from nex_agent.agent_bus import get_agent_bus
            bus = get_agent_bus()
            response_text = str(result.get("response", result))[:300]
            bus.arc_to_nex(response_text, msg_type="chat")
        except Exception:
            pass

        return result
    except Exception as e:
        return {"error": str(e), "hint": "Is Arc Agent running on port 8003?"}


def nexearch_arc_status(**kwargs) -> Dict[str, Any]:
    """Get Arc Agent status (subsystems, tools, sub-agents)."""
    try:
        from nexearch.bridge import get_arc_bridge
        bridge = get_arc_bridge()
        return bridge.status()
    except Exception as e:
        return {"error": str(e)}


def nexearch_arc_sub_agents(**kwargs) -> Dict[str, Any]:
    """Get Arc Agent's sub-agents and their status."""
    try:
        from nexearch.bridge import get_arc_bridge
        bridge = get_arc_bridge()
        return bridge.get_sub_agents()
    except Exception as e:
        return {"error": str(e)}


def nexearch_upload_clips(project_name: str, platform: str,
                            client_id: str, method: str = "playwright",
                            top_n: int = 2, caption_style: str = "",
                            title: str = "", description: str = "",
                            **kwargs) -> Dict[str, Any]:
    """Upload top clips from a NexClip project to a social account.
    Can do multi-step: find clips → apply caption style → upload.
    """
    import json
    # Step 1: Find clips from NexClip storage
    from nexearch.arc.tools.arc_tools import nexclip_get_clips
    clips_result = nexclip_get_clips(project_name, top_n)

    if "error" in clips_result:
        return clips_result

    # Step 2: Upload via Arc Agent's publisher
    from nexearch.arc.tools.arc_tools import nexclip_upload_clips
    clips_json = json.dumps(clips_result.get("top_clips", []))
    upload_result = nexclip_upload_clips(
        client_id=client_id,
        platform=platform,
        clips=clips_json,
        method=method,
        caption_style=caption_style,
        title=title,
        description=description,
    )
    return {
        "clips_found": clips_result.get("total_clips", 0),
        "clips_selected": len(clips_result.get("top_clips", [])),
        "upload_result": upload_result,
    }


def nexearch_restart_service(service: str, **kwargs) -> Dict[str, Any]:
    """Restart a NexClip/Nexearch service (backend, celery, nexearch, arc_agent, nex_agent)."""
    import subprocess, os
    allowed = {
        "backend": "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
        "celery": "celery -A app.workers.celery_app worker --loglevel=info --pool=threads",
        "nexearch": "uvicorn nexearch.main:app --reload --host 0.0.0.0 --port 8002",
        "arc_agent": "python -m nexearch.arc.server",
        "nex_agent": "python -m nex_agent.server",
    }
    if service not in allowed:
        return {"error": f"Unknown service: {service}", "allowed": list(allowed.keys())}

    # Note: actual restart requires OS-level process management
    return {
        "service": service,
        "status": "restart_requested",
        "command": allowed[service],
        "note": "Service restart must be done via process manager or start scripts",
    }


# ── Registration ───────────────────────────────────────────

def register(executor: "ToolExecutor") -> int:
    """Register all Nexearch + Arc Agent tools for Nex Agent."""
    tools = [
        ("nexearch_system_status", "Get health status of Nexearch engine and Arc Agent.", nexearch_system_status,
         {"type": "object", "properties": {}, "required": []}),

        ("nexearch_client_data", "Get all client data (scrapes, DNA, evolution, directives).", nexearch_client_data,
         {"type": "object", "properties": {"client_id": {"type": "string"}}, "required": ["client_id"]}),

        ("nexearch_client_dna", "Get Account DNA for a client on a platform.", nexearch_client_dna,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}}, "required": ["client_id", "platform"]}),

        ("nexearch_nexclip_enhancements", "Get NexClip enhancement tracking for a client.", nexearch_nexclip_enhancements,
         {"type": "object", "properties": {"client_id": {"type": "string"}}, "required": ["client_id"]}),

        ("nexearch_universal_patterns", "Get cross-client winning patterns for a platform.", nexearch_universal_patterns,
         {"type": "object", "properties": {"platform": {"type": "string", "default": "all"}}, "required": []}),

        ("nexearch_trigger_pipeline", "Trigger a full Nexearch pipeline (scrape→analyze→score→evolve→bridge→publish).", nexearch_trigger_pipeline,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}, "account_handle": {"type": "string", "default": ""}, "dry_run": {"type": "boolean", "default": True}}, "required": ["client_id", "platform"]}),

        ("nexearch_change_history", "Get change audit trail for a client.", nexearch_change_history,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "change_type": {"type": "string", "default": "all"}}, "required": ["client_id"]}),

        ("nexearch_revert_change", "Revert a change (sends negative feedback to evolution engine).", nexearch_revert_change,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "change_id": {"type": "string"}, "reason": {"type": "string", "default": ""}}, "required": ["client_id", "change_id"]}),

        ("nexearch_chat_with_arc", "Chat with Arc Agent — Nexearch's intelligence controller.", nexearch_chat_with_arc,
         {"type": "object", "properties": {"message": {"type": "string"}, "client_id": {"type": "string", "default": ""}}, "required": ["message"]}),

        ("nexearch_arc_status", "Get Arc Agent's full status (subsystems, tools, sub-agents).", nexearch_arc_status,
         {"type": "object", "properties": {}, "required": []}),

        ("nexearch_arc_sub_agents", "Get Arc Agent's sub-agents and their status.", nexearch_arc_sub_agents,
         {"type": "object", "properties": {}, "required": []}),

        ("nexearch_upload_clips", "Upload top clips from a NexClip project to social media.", nexearch_upload_clips,
         {"type": "object", "properties": {"project_name": {"type": "string"}, "platform": {"type": "string"}, "client_id": {"type": "string"}, "method": {"type": "string", "default": "playwright", "enum": ["metricool", "platform_api", "playwright"]}, "top_n": {"type": "integer", "default": 2}, "caption_style": {"type": "string", "default": ""}, "title": {"type": "string", "default": ""}, "description": {"type": "string", "default": ""}}, "required": ["project_name", "platform", "client_id"]}),

        ("nexearch_restart_service", "Restart a NexClip/Nexearch/Arc/Nex service.", nexearch_restart_service,
         {"type": "object", "properties": {"service": {"type": "string", "enum": ["backend", "celery", "nexearch", "arc_agent", "nex_agent"]}}, "required": ["service"]}),
    ]

    count = 0
    for name, desc, handler, params in tools:
        executor.register_tool(
            name=name,
            description=desc,
            handler=handler,
            parameters=params,
            category="nexearch",
        )
        count += 1

    return count
