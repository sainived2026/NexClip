"""
Nex Agent — Standalone FastAPI Server v4.0
=============================================
Runs independently on port 8001.
Does NOT depend on NexClip's main backend.

Features:
  - WebSocket chat with reconnection support
  - SSE streaming chat (backward compatible)
  - Persistent message storage via StreamingManager
  - Account-isolated conversations

Start:
    cd NexClip && python -m nex_agent.server
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

# Ensure the project root is on sys.path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from nex_agent.api import router as nex_router
from nex_agent.core import get_nex_agent
from nex_agent.request_context import reset_request_context, set_request_context
from nex_agent.websocket import ws_manager
from nex_agent.agent_bus import get_agent_bus

# ── Logging ─────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nex_agent_memory")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "nex_agent.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("nex_agent.server")

# ── Port configuration ──────────────────────────────────────────
NEX_PORT = int(os.environ.get("NEX_AGENT_PORT", "8001"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info(f"=== Nex Agent Backend v4.0 starting on port {NEX_PORT} ===")

    # Initialize agent
    agent = get_nex_agent(project_root=PROJECT_ROOT)
    agent.startup()

    # Wire broadcaster to WebSocket manager
    agent.broadcaster.set_ws_manager(ws_manager)

    # Wire streaming manager to WebSocket manager for replay support
    if agent.streaming_manager:
        ws_manager.set_streaming_manager(agent.streaming_manager)

    # Initialize the Inter-Agent Communication Bus
    agent_bus = get_agent_bus()
    agent_bus.pipeline_event("system", "Nex Agent v4.0 started — Agent Bus online")
    logger.info("AgentBus initialized and ready for monitoring")

    # Start notification monitor as background task
    agent.notification_monitor.start()
    logger.info("NotificationMonitor background task started")

    yield

    logger.info("=== Nex Agent Backend shutting down ===")
    agent.shutdown()


app = FastAPI(
    title="Nex Agent",
    description="NexClip's Living Master Intelligence — Persistent Streaming Agent",
    version="4.0.0",
    lifespan=lifespan,
)

# ── CORS — read from backend .env CORS_ORIGINS ──────────────────
_cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"http://.*",   # allow any IP for self-hosted deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount the main API router ──────────────────────────────────
app.include_router(nex_router)


# ── Health check ───────────────────────────────────────────────
@app.get("/health")
async def health():
    agent = get_nex_agent()
    return {
        "status": "ok",
        "agent": "nex",
        "version": "4.0",
        "port": NEX_PORT,
        "tools": agent.tool_executor.get_tool_count(),
        "streaming_manager": agent.streaming_manager is not None,
    }


# ── WebSocket chat with reconnection ──────────────────────────
@app.websocket("/ws/chat")
async def ws_chat(
    websocket: WebSocket,
    user_id: str = Query(default="anonymous"),
    conversation_id: str = Query(default=""),
    last_message_id: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time chat streaming with reconnection support.

    Query params:
      - user_id: The authenticated user's ID
      - conversation_id: Current conversation ID (for new messages)
      - last_message_id: Last message ID the client saw (for replay on reconnect)
    """
    await ws_manager.connect(
        websocket,
        user_id=user_id,
        conversation_id=conversation_id or None,
        last_message_id=last_message_id or None,
    )

    agent = get_nex_agent()

    # Flush any queued notifications
    queued = agent.broadcaster.get_queued_messages()
    for msg in queued:
        try:
            await websocket.send_json(msg)
        except Exception:
            break

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            conv_id = data.get("conversation_id", conversation_id)
            if conv_id:
                ws_manager.set_active_conversation(user_id, conv_id)

            if not message:
                await ws_manager.send_to_user(user_id, {
                    "type": "error", "content": "Empty message"
                })
                continue

            # Generate message IDs
            user_msg_id = str(uuid.uuid4())
            assistant_msg_id = str(uuid.uuid4())

            # Persist user message if streaming manager is available
            sm = agent.streaming_manager
            if sm and conv_id:
                try:
                    sm.save_user_message(user_msg_id, conv_id, user_id, message)
                except Exception as e:
                    logger.warning(f"Failed to save user message: {e}")

            # Create streaming response slot
            if sm and conv_id:
                try:
                    sm.create_stream(assistant_msg_id, conv_id, user_id)
                except Exception as e:
                    logger.warning(f"Failed to create stream: {e}")

            # Notify client that streaming has started
            await ws_manager.send_stream_event(user_id, assistant_msg_id, "stream_start", {
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id,
            })

            # Stream the response
            tool_calls_list = []
            full_content = ""
            context_tokens = set_request_context(user_id, conv_id)
            try:
                for chunk in agent.chat_stream(message):
                    try:
                        parsed = json.loads(chunk)
                        event_type = parsed.get("type", "token")

                        if event_type == "token":
                            token = parsed.get("content", "")
                            full_content += token
                            if sm:
                                sm.append_tokens(assistant_msg_id, token)
                            await ws_manager.broadcast_token(user_id, assistant_msg_id, token)

                        elif event_type == "tool_call":
                            tool_calls_list.append({
                                "name": parsed.get("name"),
                                "arguments": parsed.get("arguments"),
                                "result": parsed.get("result"),
                            })
                            await ws_manager.send_stream_event(
                                user_id, assistant_msg_id, "tool_call", parsed
                            )

                        elif event_type == "status":
                            await ws_manager.send_stream_event(
                                user_id, assistant_msg_id, "status", parsed
                            )

                        elif event_type == "done":
                            break

                        elif event_type == "error":
                            error_msg = parsed.get("content", "Unknown error")
                            if sm:
                                sm.finalize_stream(assistant_msg_id, error=error_msg)
                            await ws_manager.send_stream_event(
                                user_id, assistant_msg_id, "error", {"error": error_msg}
                            )
                            break
                    except json.JSONDecodeError:
                        # Raw text chunk
                        full_content += chunk
                        if sm:
                            sm.append_tokens(assistant_msg_id, chunk)
                        await ws_manager.broadcast_token(user_id, assistant_msg_id, chunk)

                # Finalize the stream as complete
                if sm:
                    sm.finalize_stream(
                        assistant_msg_id,
                        tool_calls=tool_calls_list if tool_calls_list else None,
                    )

                await ws_manager.send_stream_event(
                    user_id, assistant_msg_id, "done", {
                        "full_content": full_content,
                        "tool_calls": tool_calls_list,
                    }
                )

            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                error_msg = f"Streaming error: {str(e)}"
                if sm:
                    sm.finalize_stream(assistant_msg_id, error=error_msg)
                await ws_manager.send_stream_event(
                    user_id, assistant_msg_id, "error", {"error": error_msg}
                )
            finally:
                reset_request_context(context_tokens)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket, user_id)


# ── Agent Bus WebSocket — Real-time inter-agent monitor ────────
@app.websocket("/ws/agent-bus")
async def ws_agent_bus(websocket: WebSocket):
    """WebSocket endpoint for the Agent Monitor terminal."""
    bus = get_agent_bus()
    await bus.connect_monitor(websocket)
    try:
        while True:
            # Keep connection alive; client may send filter commands
            data = await websocket.receive_text()
            # Future: handle filter commands from the client
    except WebSocketDisconnect:
        bus.disconnect_monitor(websocket)
    except Exception:
        bus.disconnect_monitor(websocket)


# ── Agent Bus REST API — Fetch recent messages ────────────────
@app.get("/api/nex/agent-bus/messages")
async def get_bus_messages(
    limit: int = Query(default=50, le=200),
    agent: str = Query(default=""),
    msg_type: str = Query(default=""),
):
    """Get recent inter-agent communication messages."""
    bus = get_agent_bus()
    if agent:
        return {"messages": bus.get_by_agent(agent, limit)}
    if msg_type:
        return {"messages": bus.get_by_type(msg_type, limit)}
    return {"messages": bus.get_recent(limit)}


# ── Main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "nex_agent.server:app",
        host="0.0.0.0",
        port=NEX_PORT,
    )
