"""
Arc Agent — Standalone FastAPI Server
=========================================
Runs independently on port 8003.
Provides WebSocket chat, REST API, and SSE streaming.

Start:
    cd NexClip && python -m nexearch.arc.server
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

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

# Ensure project root is on path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
BACKEND_PATH = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from nexearch.arc.api import router as arc_router
from nexearch.arc.core import get_arc_agent
from nexearch.arc.websocket import arc_ws_manager
from nex_agent.response_validator import ResponseValidator

_validator = ResponseValidator()

# ── Logging ─────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arc_agent_memory")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "arc_agent.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("arc_agent.server")

# ── Port configuration ──────────────────────────────────────────
ARC_PORT = int(os.environ.get("ARC_AGENT_PORT", "8003"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info(f"=== Arc Agent Backend v1.0 starting on port {ARC_PORT} ===")

    # Initialize agent
    agent = get_arc_agent()
    agent.startup()

    # Wire streaming manager to WebSocket manager
    if agent.streaming_manager:
        arc_ws_manager.set_streaming_manager(agent.streaming_manager)

    yield

    logger.info("=== Arc Agent Backend shutting down ===")
    agent.shutdown()


app = FastAPI(
    title="Arc Agent",
    description="Nexearch's Living Intelligence Controller — Self-Evolving Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────
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

# ── Mount API router ────────────────────────────────────────────
app.include_router(arc_router)


# ── Health check ────────────────────────────────────────────────
@app.get("/health")
async def health():
    agent = get_arc_agent()
    return {
        "status": "ok",
        "agent": "arc",
        "version": "1.0",
        "port": ARC_PORT,
        "tools": agent.tool_executor.get_tool_count() if agent.tool_executor else 0,
        "streaming_manager": agent.streaming_manager is not None,
    }


# ── WebSocket chat ─────────────────────────────────────────────
@app.websocket("/ws/chat")
async def ws_chat(
    websocket: WebSocket,
    user_id: str = Query(default="anonymous"),
    conversation_id: str = Query(default=""),
    last_message_id: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time Arc Agent chat with streaming.
    Mirrors Nex Agent's WebSocket chat protocol.
    """
    await arc_ws_manager.connect(
        websocket,
        user_id=user_id,
        last_message_id=last_message_id or None,
    )

    agent = get_arc_agent()

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            conv_id = data.get("conversation_id", conversation_id)
            client_id = data.get("client_id", "")

            if not message:
                await arc_ws_manager.send_to_user(user_id, {
                    "type": "error", "content": "Empty message",
                })
                continue

            # Generate message IDs
            user_msg_id = str(uuid.uuid4())
            assistant_msg_id = str(uuid.uuid4())

            # Persist user message
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
            await arc_ws_manager.send_stream_event(user_id, assistant_msg_id, "stream_start", {
                "user_message_id": user_msg_id,
                "assistant_message_id": assistant_msg_id,
            })

            # Build context
            context = {}
            if client_id:
                try:
                    from nexearch.data.client_store import ClientDataStore
                    store = ClientDataStore(client_id)
                    context["client_context"] = store.get_client_summary()
                except Exception:
                    pass

            # Stream the response
            tool_calls_list = []
            full_content = ""
            try:
                for chunk in agent.chat_stream(message, context=context):
                    try:
                        parsed = json.loads(chunk)
                        event_type = parsed.get("type", "token")

                        if event_type == "token":
                            token = parsed.get("content", "")
                            full_content += token
                            if sm:
                                sm.append_tokens(assistant_msg_id, token)
                            await arc_ws_manager.broadcast_token(user_id, assistant_msg_id, token)

                        elif event_type == "tool_call":
                            tool_calls_list.append({
                                "name": parsed.get("name"),
                                "arguments": parsed.get("arguments"),
                                "result": parsed.get("result"),
                            })
                            await arc_ws_manager.send_stream_event(
                                user_id, assistant_msg_id, "tool_call", parsed
                            )

                        elif event_type == "status":
                            await arc_ws_manager.send_stream_event(
                                user_id, assistant_msg_id, "status", parsed
                            )

                        elif event_type == "done":
                            break

                        elif event_type == "error":
                            error_msg = parsed.get("content", "Unknown error")
                            if sm:
                                sm.finalize_stream(assistant_msg_id, error=error_msg)
                            await arc_ws_manager.send_stream_event(
                                user_id, assistant_msg_id, "error", {"error": error_msg}
                            )
                            break

                    except json.JSONDecodeError:
                        full_content += chunk
                        if sm:
                            sm.append_tokens(assistant_msg_id, chunk)
                        await arc_ws_manager.broadcast_token(user_id, assistant_msg_id, chunk)

                # Build a safe final answer so leaked prompt text never reaches the UI
                thinking_content, clean_content = _validator.sanitize_chat_response(full_content)

                # Finalize
                if sm:
                    sm.finalize_stream(
                        assistant_msg_id,
                        tool_calls=tool_calls_list if tool_calls_list else None,
                        final_content=clean_content,
                        thinking_content=thinking_content,
                    )

                await arc_ws_manager.send_stream_event(
                    user_id, assistant_msg_id, "done", {
                        "full_content": clean_content,
                        "thinking_content": thinking_content,
                        "tool_calls": tool_calls_list,
                    }
                )

            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                error_msg = f"Streaming error: {str(e)}"
                if sm:
                    sm.finalize_stream(assistant_msg_id, error=error_msg)
                await arc_ws_manager.send_stream_event(
                    user_id, assistant_msg_id, "error", {"error": error_msg}
                )

    except WebSocketDisconnect:
        arc_ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        arc_ws_manager.disconnect(websocket, user_id)


# ── Main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "nexearch.arc.server:app",
        host="0.0.0.0",
        port=ARC_PORT,
    )
