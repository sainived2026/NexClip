"""
Nex Agent — FastAPI API Router v4.0
========================================
Endpoints for chat (SSE streaming), status, history,
conversations (CRUD with user isolation), commands,
agent management, knowledge queries, file operations,
skills, and workflows.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

import logging

# Ensure backend imports work
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logger = logging.getLogger("nex_agent.api")

router = APIRouter(prefix="/api/nex", tags=["Nex Agent"])


# ── Request / Response Models ───────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str = Field(default="")


class CommandRequest(BaseModel):
    target_agent: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class AlertRequest(BaseModel):
    severity: str = "medium"
    source: str = "admin"
    issue: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)


class FileWriteRequest(BaseModel):
    path: str
    content: str


class FileEditRequest(BaseModel):
    path: str
    target: str
    replacement: str


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str
    steps: str


# ── Auth dependency for Nex Agent ───────────────────────────────

def _extract_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Extract user_id from JWT Bearer token.
    Falls back to 'anonymous' if no token is provided (backward compat).
    """
    if not authorization or not authorization.startswith("Bearer "):
        return "anonymous"

    token = authorization.replace("Bearer ", "")
    try:
        from app.core.security import decode_access_token
        payload = decode_access_token(token)
        user_id = payload.get("sub", "anonymous")
        return user_id
    except Exception:
        return "anonymous"


# ── Lazy Agent Access ───────────────────────────────────────────

def _get_agent():
    """Get the Nex Agent singleton (lazy initialization)."""
    from nex_agent.core import get_nex_agent
    return get_nex_agent()


# ══════════════════════════════════════════════════════════════════
# 1. CONVERSATIONS (Account-Isolated CRUD)
# ══════════════════════════════════════════════════════════════════

@router.get("/conversations")
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(_extract_user_id),
):
    """Returns ONLY the authenticated user's conversations."""
    agent = _get_agent()
    sm = agent.streaming_manager
    if not sm:
        return JSONResponse(content={"conversations": []})

    conversations = sm.list_conversations(user_id, limit=limit, offset=offset)
    return JSONResponse(content={"conversations": conversations})


@router.post("/conversations")
async def create_conversation(user_id: str = Depends(_extract_user_id)):
    """Create a new conversation for the authenticated user."""
    agent = _get_agent()
    sm = agent.streaming_manager
    if not sm:
        raise HTTPException(status_code=503, detail="Streaming manager not available")

    # Get active model name
    model = "unknown"
    try:
        from nex_agent.llm_provider import get_llm_provider
        model = get_llm_provider().get_active_model()
    except Exception:
        pass

    conv_id = sm.create_conversation(user_id, model_used=model)
    return JSONResponse(content={"id": conv_id})


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user_id: str = Depends(_extract_user_id),
):
    """Get messages for a conversation. Verifies ownership."""
    agent = _get_agent()
    sm = agent.streaming_manager
    if not sm:
        raise HTTPException(status_code=503, detail="Streaming manager not available")

    messages = sm.get_conversation_messages(conversation_id, user_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")

    return JSONResponse(content={"messages": messages})


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(_extract_user_id),
):
    """Soft-delete a conversation. Verifies ownership."""
    agent = _get_agent()
    sm = agent.streaming_manager
    if not sm:
        raise HTTPException(status_code=503, detail="Streaming manager not available")

    deleted = sm.delete_conversation(conversation_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")

    return JSONResponse(content={"deleted": True})


# ══════════════════════════════════════════════════════════════════
# 2. CHAT (SSE streaming — backward compatible)
# ══════════════════════════════════════════════════════════════════

@router.post("/chat")
async def chat_stream(
    req: ChatRequest,
    user_id: str = Depends(_extract_user_id),
):
    """Chat with Nex Agent via Server-Sent Events."""
    agent = _get_agent()
    sm = agent.streaming_manager

    # Generate IDs
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

    # Persist user message
    if sm and req.conversation_id:
        try:
            sm.save_user_message(user_msg_id, req.conversation_id, user_id, req.message)
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")

    # Create streaming slot
    if sm and req.conversation_id:
        try:
            sm.create_stream(assistant_msg_id, req.conversation_id, user_id)
        except Exception as e:
            logger.warning(f"Failed to create stream: {e}")

    async def event_generator():
        from nex_agent.request_context import reset_request_context, set_request_context
        from nex_agent.response_validator import ResponseValidator

        full_content = ""
        tool_calls_list = []
        validator = ResponseValidator()
        context_tokens = set_request_context(user_id, req.conversation_id)
        try:
            for chunk in agent.chat_stream(req.message):
                try:
                    parsed = json.loads(chunk)
                    event_type = parsed.get("type", "token")

                    if event_type == "token":
                        token = parsed.get("content", "")
                        full_content += token
                        if sm:
                            sm.append_tokens(assistant_msg_id, token)

                    elif event_type == "tool_call":
                        tool_calls_list.append({
                            "name": parsed.get("name"),
                            "arguments": parsed.get("arguments"),
                            "result": parsed.get("result"),
                        })

                except json.JSONDecodeError:
                    pass

                yield f"data: {chunk}\n\n"

            # Finalize
            thinking_content, clean_content = validator.sanitize_chat_response(full_content)
            if sm:
                sm.finalize_stream(
                    assistant_msg_id,
                    tool_calls=tool_calls_list if tool_calls_list else None,
                    final_content=clean_content,
                    rich_type="chat_reasoning" if thinking_content else None,
                    rich_data={"thinking_content": thinking_content} if thinking_content else None,
                )

            done_event = json.dumps({
                "type": "done",
                "full_content": clean_content,
                "thinking_content": thinking_content,
                "tool_calls": tool_calls_list,
            })
            yield f"data: {done_event}\n\n"

        except Exception as e:
            error = json.dumps({"type": "error", "content": str(e)})
            if sm:
                sm.finalize_stream(assistant_msg_id, error=str(e))
            yield f"data: {error}\n\n"
        finally:
            reset_request_context(context_tokens)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/sync")
async def chat_sync(req: ChatRequest, user_id: str = Depends(_extract_user_id)):
    """Non-streaming chat endpoint (returns full response)."""
    agent = _get_agent()
    from nex_agent.request_context import reset_request_context, set_request_context

    context_tokens = set_request_context(user_id, req.conversation_id)
    try:
        result = agent.chat(req.message)
    finally:
        reset_request_context(context_tokens)
    return JSONResponse(content=result)


# ══════════════════════════════════════════════════════════════════
# 3. STATUS & HISTORY
# ══════════════════════════════════════════════════════════════════

@router.get("/status")
async def get_status():
    """Get Nex Agent's current status and system health."""
    agent = _get_agent()
    return JSONResponse(content=agent.get_status())


@router.get("/history")
async def get_history(limit: int = 50):
    """Get conversation history (in-memory — backward compat)."""
    agent = _get_agent()
    history = agent.get_history(limit=limit)
    return JSONResponse(content={"messages": history})


@router.delete("/history")
async def clear_history():
    """Clear conversation and start fresh session."""
    agent = _get_agent()
    agent.clear_history()
    return JSONResponse(content={"status": "ok", "message": "Conversation cleared"})


@router.get("/model")
async def get_model_info():
    """Get the currently active LLM model."""
    try:
        from nex_agent.llm_provider import get_llm_provider
        provider = get_llm_provider()
        return JSONResponse(content={
            "active_model": provider.get_active_model(),
            "providers": provider.get_provider_status(),
        })
    except Exception:
        return JSONResponse(content={"active_model": "Unknown", "providers": []})


# ══════════════════════════════════════════════════════════════════
# 4. COMMANDS & ALERTS
# ══════════════════════════════════════════════════════════════════

@router.post("/command")
async def send_command(req: CommandRequest):
    """Send a command to an agent via the command bus."""
    agent = _get_agent()
    message_id = agent.execute_command(req.target_agent, req.action, req.params)
    if not message_id:
        raise HTTPException(status_code=403, detail="Command authority denied")
    return JSONResponse(content={"status": "ok", "message_id": message_id})


@router.post("/alert")
async def send_alert(req: AlertRequest):
    """Submit an alert to Nex Agent's decision engine."""
    agent = _get_agent()
    result = agent.handle_alert(req.severity, req.source, req.issue, req.context)
    return JSONResponse(content=result)


@router.get("/agents")
async def get_agents():
    """Get all registered agents and their status."""
    agent = _get_agent()
    agents = agent.bus.get_all_agents()
    return JSONResponse(content={"agents": agents})


# ══════════════════════════════════════════════════════════════════
# 5. KNOWLEDGE INDEX
# ══════════════════════════════════════════════════════════════════

@router.get("/knowledge")
async def get_knowledge(q: str = ""):
    """Query the codebase knowledge index."""
    agent = _get_agent()
    if q:
        results = agent.knowledge.query(q, limit=10)
        return JSONResponse(content={"results": results, "query": q})
    else:
        summary = agent.knowledge.get_summary()
        return JSONResponse(content={"summary": summary})


@router.post("/knowledge/refresh")
async def refresh_knowledge():
    """Force a codebase re-scan."""
    agent = _get_agent()
    count = agent.refresh_knowledge()
    return JSONResponse(content={"status": "ok", "files_indexed": count})


# ══════════════════════════════════════════════════════════════════
# 6. FILE OPERATIONS
# ══════════════════════════════════════════════════════════════════

@router.get("/files/read")
async def read_file(path: str):
    """Read a file from the NexClip project."""
    agent = _get_agent()
    result = agent.file_operator.read_file(path)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(content=result)


@router.post("/files/write")
async def write_file(req: FileWriteRequest):
    """Write content to a file."""
    agent = _get_agent()
    result = agent.file_operator.write_file(req.path, req.content)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return JSONResponse(content=result)


@router.post("/files/edit")
async def edit_file(req: FileEditRequest):
    """Replace a target string in a file."""
    agent = _get_agent()
    result = agent.file_operator.edit_file(req.path, req.target, req.replacement)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return JSONResponse(content=result)


@router.get("/files/list")
async def list_directory(path: str = "."):
    """List contents of a directory."""
    agent = _get_agent()
    result = agent.file_operator.list_directory(path)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(content=result)


@router.get("/files/search")
async def search_files(q: str, ext: str = ""):
    """Search files by name pattern."""
    agent = _get_agent()
    extensions = [e.strip() for e in ext.split(",") if e.strip()] if ext else None
    results = agent.file_operator.search_files(q, extensions)
    return JSONResponse(content={"results": results, "query": q})


# ══════════════════════════════════════════════════════════════════
# 7. SKILLS
# ══════════════════════════════════════════════════════════════════

@router.get("/skills")
async def list_skills():
    """List all available skills."""
    agent = _get_agent()
    return JSONResponse(content={"skills": agent.skill_loader.list_skills()})


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    """Get a specific skill by ID."""
    agent = _get_agent()
    skill = agent.skill_loader.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return JSONResponse(content=skill)


# ══════════════════════════════════════════════════════════════════
# 8. WORKFLOWS
# ══════════════════════════════════════════════════════════════════

@router.get("/workflows")
async def list_workflows():
    """List all workflows."""
    agent = _get_agent()
    return JSONResponse(content={"workflows": agent.workflow_manager.list_workflows()})


@router.get("/workflows/{name}")
async def get_workflow(name: str):
    """Get a workflow by name."""
    agent = _get_agent()
    wf = agent.workflow_manager.get_workflow(name)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return JSONResponse(content=wf)


@router.post("/workflows")
async def create_workflow(req: WorkflowCreateRequest):
    """Create a new workflow."""
    agent = _get_agent()
    result = agent.workflow_manager.create_workflow(req.name, req.description, req.steps)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return JSONResponse(content=result)


@router.delete("/workflows/{name}")
async def delete_workflow(name: str):
    """Delete a workflow."""
    agent = _get_agent()
    result = agent.workflow_manager.delete_workflow(name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return JSONResponse(content=result)


# ══════════════════════════════════════════════════════════════════
# 9. LIVE FEED
# ══════════════════════════════════════════════════════════════════

@router.get("/stream")
async def agent_stream():
    """Live agent activity feed via SSE."""
    agent = _get_agent()

    async def event_generator():
        import asyncio
        last_msg_count = 0
        while True:
            messages = agent.bus.get_recent_messages(5)
            if len(messages) > last_msg_count:
                new_msgs = messages[last_msg_count:]
                for msg in new_msgs:
                    yield f"data: {json.dumps(msg)}\n\n"
                last_msg_count = len(messages)
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ══════════════════════════════════════════════════════════════════
# 10. NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════

@router.get("/notifications")
async def get_notifications(unread_only: bool = False):
    """Get processing notifications (completion/failure alerts)."""
    notif_dir = Path(__file__).resolve().parent / "nex_agent_memory" / "notifications"
    if not notif_dir.exists():
        return JSONResponse(content={"notifications": []})

    notifications = []
    for f in sorted(notif_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if unread_only and data.get("read", False):
                continue
            notifications.append(data)
        except Exception:
            continue

    return JSONResponse(content={"notifications": notifications[:50]})


@router.patch("/notifications/read-all")
async def mark_all_notifications_read():
    """Mark all notifications as read."""
    notif_dir = Path(__file__).resolve().parent / "nex_agent_memory" / "notifications"
    if not notif_dir.exists():
        return JSONResponse(content={"status": "ok", "marked": 0})

    marked = 0
    for f in notif_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if not data.get("read"):
                data["read"] = True
                f.write_text(json.dumps(data, indent=2), encoding="utf-8")
                marked += 1
        except Exception:
            continue

    return JSONResponse(content={"status": "ok", "marked": marked})


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark a notification as read."""
    notif_dir = Path(__file__).resolve().parent / "nex_agent_memory" / "notifications"
    notif_path = notif_dir / f"{notification_id}.json"

    if not notif_path.exists():
        raise HTTPException(status_code=404, detail="Notification not found")

    data = json.loads(notif_path.read_text(encoding="utf-8"))
    data["read"] = True
    notif_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return JSONResponse(content={"status": "ok"})




@router.delete("/notifications")
async def clear_notifications():
    """Clear all notifications."""
    notif_dir = Path(__file__).resolve().parent / "nex_agent_memory" / "notifications"
    if notif_dir.exists():
        for f in notif_dir.glob("*.json"):
            f.unlink(missing_ok=True)
    return JSONResponse(content={"status": "ok", "message": "Notifications cleared"})

