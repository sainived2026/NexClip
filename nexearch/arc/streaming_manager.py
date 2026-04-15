"""
Arc Agent — Streaming Manager
=================================
Persistent message storage for reconnection support.
Tracks all streamed messages so clients can replay on reconnect.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class ArcStreamingManager:
    """
    Persistent streaming manager for Arc Agent.
    Stores messages in JSON files for durability.
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        default_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "arc_agent_memory", "streams"
        )
        self._storage_path = Path(storage_path or default_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._active_streams: Dict[str, Dict[str, Any]] = {}

    def create_stream(self, message_id: str, conversation_id: str,
                       user_id: str) -> None:
        """Create a new streaming response slot."""
        self._active_streams[message_id] = {
            "id": message_id,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "assistant",
            "content": "",
            "status": "streaming",
            "tool_calls": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def append_tokens(self, message_id: str, tokens: str) -> None:
        """Append tokens to an active stream."""
        stream = self._active_streams.get(message_id)
        if stream:
            stream["content"] += tokens

    def finalize_stream(self, message_id: str,
                         tool_calls: Optional[List] = None,
                         error: Optional[str] = None) -> None:
        """Finalize a stream and persist to disk."""
        stream = self._active_streams.get(message_id)
        if not stream:
            return

        stream["status"] = "error" if error else "complete"
        if error:
            stream["error"] = error
        if tool_calls:
            stream["tool_calls"] = tool_calls
        stream["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Persist
        self._persist_message(stream)
        del self._active_streams[message_id]

    def save_user_message(self, message_id: str, conversation_id: str,
                            user_id: str, content: str) -> None:
        """Save a user message."""
        msg = {
            "id": message_id,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": "user",
            "content": content,
            "status": "complete",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._persist_message(msg)

    def create_conversation(self, conversation_id: str, user_id: str = "admin") -> None:
        """Create an empty conversation file if it does not already exist."""
        conv_path = self._storage_path / f"{conversation_id}.json"
        if conv_path.exists():
            return
        with open(conv_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

    def list_conversations(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List conversation metadata expected by the frontend chat UI."""
        conversations: List[Dict[str, Any]] = []
        for conv_path in self._storage_path.glob("*.json"):
            try:
                with open(conv_path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except Exception:
                messages = []

            first_user = next((m for m in messages if m.get("role") == "user" and m.get("content")), None)
            title = "New Chat"
            if first_user:
                content = str(first_user.get("content", "")).strip()
                if content:
                    title = content[:60] + ("..." if len(content) > 60 else "")

            created_at = (
                (messages[0].get("created_at") if messages else None)
                or datetime.fromtimestamp(conv_path.stat().st_ctime, tz=timezone.utc).isoformat()
            )
            updated_at = (
                (messages[-1].get("created_at") if messages else None)
                or datetime.fromtimestamp(conv_path.stat().st_mtime, tz=timezone.utc).isoformat()
            )

            conversations.append({
                "id": conv_path.stem,
                "title": title,
                "created_at": created_at,
                "updated_at": updated_at,
                "message_count": len(messages),
            })

        conversations.sort(key=lambda conv: conv.get("updated_at", ""), reverse=True)
        return conversations[offset: offset + limit]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and any active streams tied to it."""
        conv_path = self._storage_path / f"{conversation_id}.json"
        deleted = False
        if conv_path.exists():
            conv_path.unlink()
            deleted = True

        for message_id, stream in list(self._active_streams.items()):
            if stream.get("conversation_id") == conversation_id:
                del self._active_streams[message_id]

        return deleted

    def get_messages_after(self, last_message_id: str) -> List[Dict[str, Any]]:
        """Get messages after a specific message ID (for reconnection replay)."""
        # Load all messages and find those after the given ID
        messages = self._load_recent_messages(limit=100)
        found = False
        result = []
        for msg in messages:
            if found:
                result.append(msg)
            if msg.get("message_id") == last_message_id:
                found = True
        return result

    def get_conversation_messages(self, conversation_id: str,
                                    limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages for a conversation."""
        conv_path = self._storage_path / f"{conversation_id}.json"
        if conv_path.exists():
            try:
                with open(conv_path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                normalized = []
                for msg in messages[-limit:]:
                    normalized.append({
                        **msg,
                        "id": msg.get("id") or msg.get("message_id", str(uuid.uuid4())),
                        "role": msg.get("role") or ("assistant" if msg.get("message_id") else "user"),
                    })
                return normalized
            except Exception:
                pass
        return []

    def cleanup_stale_streams(self, max_age_seconds: int = 300) -> int:
        """Clean up streams that were never finalized."""
        cleaned = 0
        now = datetime.now(timezone.utc)
        for msg_id in list(self._active_streams.keys()):
            stream = self._active_streams[msg_id]
            try:
                created = datetime.fromisoformat(stream["created_at"])
                if (now - created).total_seconds() > max_age_seconds:
                    self.finalize_stream(msg_id, error="Stream timed out")
                    cleaned += 1
            except Exception:
                continue
        return cleaned

    def _persist_message(self, message: Dict[str, Any]) -> None:
        """Persist a message to its conversation file."""
        conv_id = message.get("conversation_id", "default")
        conv_path = self._storage_path / f"{conv_id}.json"

        messages = []
        if conv_path.exists():
            try:
                with open(conv_path, "r", encoding="utf-8") as f:
                    messages = json.load(f)
            except Exception:
                messages = []

        messages.append(message)
        with open(conv_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False, default=str)

    def _load_recent_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Load recent messages across all conversations."""
        all_messages = []
        for f in sorted(self._storage_path.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    messages = json.load(fp)
                all_messages.extend(messages)
                if len(all_messages) >= limit:
                    break
            except Exception:
                continue
        return all_messages[-limit:]
