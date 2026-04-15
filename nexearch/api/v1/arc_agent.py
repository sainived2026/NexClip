"""
Nexearch — Arc Agent Routes
Chat interface and action execution for the Arc Agent controller.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from loguru import logger

router = APIRouter(prefix="/arc", tags=["Arc Agent"])


@router.post("/chat", summary="Chat with Arc Agent")
async def chat_with_arc(data: Dict[str, Any]):
    """
    Send a message to Arc Agent and get a response.

    Body:
    - message: str (required)
    - conversation_id: str (optional, for session continuity)
    - client_id: str (optional, for client context)
    """
    message = data.get("message", "")
    if not message:
        raise HTTPException(400, "Message is required")

    from nexearch.agents.arc_agent import get_arc_agent

    arc = get_arc_agent()

    # Build client context if client_id provided
    client_context = None
    client_id = data.get("client_id")
    if client_id:
        try:
            from nexearch.data.client_store import ClientDataStore
            from nexearch.data.nexclip_client_store import NexClipClientStore
            store = ClientDataStore(client_id)
            nexclip_store = NexClipClientStore(client_id)
            client_context = {
                "client_summary": store.get_client_summary(),
                "nexclip_report": nexclip_store.generate_enhancement_report(),
            }
        except Exception:
            pass

    response = arc.chat(
        message=message,
        conversation_id=data.get("conversation_id"),
        client_context=client_context,
    )

    return response


@router.post("/execute", summary="Execute an Arc Agent action")
async def execute_action(data: Dict[str, Any]):
    """Execute a specific Arc Agent action."""
    action = data.get("action")
    client_id = data.get("client_id", "")

    if not action:
        raise HTTPException(400, "Action is required")

    from nexearch.agents.arc_agent import get_arc_agent
    arc = get_arc_agent()

    result = await arc.execute_action(
        action=action,
        client_id=client_id,
        credentials=data.get("credentials"),
    )
    return result


@router.get("/history/{conversation_id}", summary="Get conversation history")
async def get_history(conversation_id: str):
    """Get Arc Agent conversation history."""
    from nexearch.agents.arc_agent import get_arc_agent
    arc = get_arc_agent()
    history = arc.get_conversation_history(conversation_id)
    return {"conversation_id": conversation_id, "messages": history}
