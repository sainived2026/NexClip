from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Dict, Tuple


_current_user_id: ContextVar[str] = ContextVar("nex_agent_current_user_id", default="")
_current_conversation_id: ContextVar[str] = ContextVar(
    "nex_agent_current_conversation_id",
    default="",
)


def set_request_context(user_id: str = "", conversation_id: str = "") -> Tuple[Token, Token]:
    """Bind the active Nex request context for downstream tool calls."""
    return (
        _current_user_id.set(user_id or ""),
        _current_conversation_id.set(conversation_id or ""),
    )


def reset_request_context(tokens: Tuple[Token, Token]) -> None:
    """Restore the previous request context."""
    user_token, conversation_token = tokens
    _current_user_id.reset(user_token)
    _current_conversation_id.reset(conversation_token)


def get_request_context() -> Dict[str, str]:
    """Return the current user/conversation context for this execution path."""
    return {
        "user_id": _current_user_id.get(),
        "conversation_id": _current_conversation_id.get(),
    }
