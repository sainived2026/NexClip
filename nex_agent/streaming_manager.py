"""
Nex Agent — Streaming Manager
=================================
Manages all active and completed streaming responses with incremental
database persistence. Every token is persisted so clients can reconnect
at any time and receive the full response.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path for backend imports
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("nex_agent.streaming_manager")


@dataclass
class ActiveStream:
    """In-memory representation of a currently streaming response."""
    message_id: str
    conversation_id: str
    user_id: str
    buffer: str = ""
    token_count: int = 0
    _flush_threshold: int = 50  # Flush to DB every N characters


@dataclass
class StreamState:
    """The state of a message — returned to reconnecting clients."""
    status: str          # 'streaming' | 'complete' | 'error' | 'not_found'
    content: str
    message_id: str
    tool_calls: List[Dict] = field(default_factory=list)
    error_detail: str = ""


class StreamingManager:
    """
    Manages all active and completed streaming responses.
    Every token is persisted to the database as it is generated.
    Clients can reconnect at any time and receive the full response.
    """

    def __init__(self, db_path: str) -> None:
        self.active_streams: Dict[str, ActiveStream] = {}
        self._db_path = db_path
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
        self._SessionLocal = sessionmaker(bind=self._engine)
        logger.info(f"StreamingManager initialized with DB: {db_path}")

    def _get_session(self) -> Session:
        return self._SessionLocal()

    # ── Stream Lifecycle ────────────────────────────────────────

    def create_stream(
        self,
        message_id: str,
        conversation_id: str,
        user_id: str,
    ) -> ActiveStream:
        """
        Create a new streaming response slot in the database before
        any tokens are generated. Status = 'streaming'.
        """
        now = datetime.now(timezone.utc)

        session = self._get_session()
        try:
            session.execute(text("""
                INSERT INTO nex_messages
                    (id, conversation_id, user_id, role, content, status, created_at, updated_at, token_count)
                VALUES
                    (:id, :conv_id, :user_id, 'assistant', '', 'streaming', :now, :now, 0)
            """), {
                "id": message_id,
                "conv_id": conversation_id,
                "user_id": user_id,
                "now": now,
            })
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create stream row: {e}")
            raise
        finally:
            session.close()

        stream = ActiveStream(
            message_id=message_id,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        self.active_streams[message_id] = stream
        logger.debug(f"Created stream {message_id} for conversation {conversation_id}")
        return stream

    def append_tokens(self, message_id: str, token: str) -> None:
        """
        Append token(s) to the in-memory buffer.
        Flushes to DB periodically to balance performance and durability.
        """
        stream = self.active_streams.get(message_id)
        if not stream:
            return

        stream.buffer += token
        stream.token_count += len(token)

        # Flush to DB periodically
        if stream.token_count % stream._flush_threshold < len(token):
            self._flush_to_db(stream)

    def _flush_to_db(self, stream: ActiveStream) -> None:
        """Write current buffer to database."""
        session = self._get_session()
        try:
            session.execute(text("""
                UPDATE nex_messages
                SET content = :content, updated_at = :now, token_count = :tc
                WHERE id = :id
            """), {
                "content": stream.buffer,
                "now": datetime.now(timezone.utc),
                "tc": stream.token_count,
                "id": stream.message_id,
            })
            session.commit()
        except Exception as e:
            session.rollback()
            logger.warning(f"DB flush failed for stream {stream.message_id}: {e}")
        finally:
            session.close()

    def finalize_stream(
        self,
        message_id: str,
        tool_calls: Optional[List[Dict]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Mark a stream as complete or errored. Final DB write.
        """
        stream = self.active_streams.pop(message_id, None)
        if not stream:
            # Stream not in memory — update DB directly (crashed recovery)
            self._finalize_db_only(message_id, "", tool_calls, error)
            return

        final_content = stream.buffer
        status = "complete" if not error else "error"
        now = datetime.now(timezone.utc)

        session = self._get_session()
        try:
            session.execute(text("""
                UPDATE nex_messages
                SET content = :content, status = :status, tool_calls = :tc,
                    error_detail = :err, completed_at = :now, updated_at = :now,
                    token_count = :token_count
                WHERE id = :id
            """), {
                "content": final_content,
                "status": status,
                "tc": json.dumps(tool_calls) if tool_calls else None,
                "err": error,
                "now": now,
                "token_count": stream.token_count,
                "id": message_id,
            })

            # Update conversation's message_count and updated_at
            session.execute(text("""
                UPDATE nex_conversations
                SET message_count = (
                    SELECT COUNT(*) FROM nex_messages WHERE conversation_id = :conv_id
                ), updated_at = :now
                WHERE id = :conv_id
            """), {"conv_id": stream.conversation_id, "now": now})

            session.commit()
            logger.debug(f"Finalized stream {message_id} as {status}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to finalize stream {message_id}: {e}")
        finally:
            session.close()

    def _finalize_db_only(
        self, message_id: str, content: str,
        tool_calls: Optional[List[Dict]], error: Optional[str]
    ) -> None:
        """Fallback finalize when stream is not in memory."""
        status = "complete" if not error else "error"
        now = datetime.now(timezone.utc)
        session = self._get_session()
        try:
            session.execute(text("""
                UPDATE nex_messages
                SET status = :status, error_detail = :err,
                    completed_at = :now, updated_at = :now
                WHERE id = :id AND status = 'streaming'
            """), {"status": status, "err": error, "now": now, "id": message_id})
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    # ── Stream State Query ──────────────────────────────────────

    def get_stream_state(self, message_id: str) -> StreamState:
        """
        Returns current state of a message — for reconnecting clients.
        Checks in-memory active streams first, then falls back to DB.
        """
        # Check in-memory active streams first
        if message_id in self.active_streams:
            stream = self.active_streams[message_id]
            return StreamState(
                status="streaming",
                content=stream.buffer,
                message_id=message_id,
            )

        # Fall back to database
        session = self._get_session()
        try:
            result = session.execute(text("""
                SELECT content, status, tool_calls, error_detail
                FROM nex_messages WHERE id = :id
            """), {"id": message_id}).fetchone()

            if not result:
                return StreamState(status="not_found", content="", message_id=message_id)

            return StreamState(
                status=result[1],
                content=result[0] or "",
                message_id=message_id,
                tool_calls=json.loads(result[2]) if result[2] else [],
                error_detail=result[3] or "",
            )
        finally:
            session.close()

    # ── Conversation CRUD ───────────────────────────────────────

    def create_conversation(self, user_id: str, model_used: str = "") -> str:
        """Create a new conversation for the given user. Returns conversation ID."""
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        session = self._get_session()
        try:
            session.execute(text("""
                INSERT INTO nex_conversations
                    (id, user_id, title, model_used, created_at, updated_at, is_deleted, message_count)
                VALUES
                    (:id, :user_id, '', :model, :now, :now, 0, 0)
            """), {"id": conv_id, "user_id": user_id, "model": model_used, "now": now})
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create conversation: {e}")
            raise
        finally:
            session.close()

        return conv_id

    def save_user_message(self, message_id: str, conversation_id: str, user_id: str, content: str) -> None:
        """Save a user message (not streaming — immediately complete)."""
        now = datetime.now(timezone.utc)
        session = self._get_session()
        try:
            session.execute(text("""
                INSERT INTO nex_messages
                    (id, conversation_id, user_id, role, content, status, created_at, updated_at, completed_at)
                VALUES
                    (:id, :conv_id, :user_id, 'user', :content, 'complete', :now, :now, :now)
            """), {
                "id": message_id,
                "conv_id": conversation_id,
                "user_id": user_id,
                "content": content,
                "now": now,
            })

            # Auto-title: set conversation title from first user message
            session.execute(text("""
                UPDATE nex_conversations
                SET title = CASE WHEN title = '' THEN :title ELSE title END,
                    updated_at = :now,
                    message_count = message_count + 1
                WHERE id = :conv_id
            """), {
                "title": content[:60] + ("..." if len(content) > 60 else ""),
                "now": now,
                "conv_id": conversation_id,
            })
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save user message: {e}")
            raise
        finally:
            session.close()

    def save_assistant_message(
        self,
        message_id: str,
        conversation_id: str,
        user_id: str,
        content: str,
        rich_type: str = "",
        rich_data: Optional[Dict[str, Any]] = None,
        error_detail: Optional[str] = None,
    ) -> None:
        """Persist a complete assistant message outside the normal streaming flow."""
        now = datetime.now(timezone.utc)
        session = self._get_session()
        try:
            session.execute(text("""
                INSERT INTO nex_messages
                    (id, conversation_id, user_id, role, content, status, rich_type, rich_data,
                     error_detail, created_at, updated_at, completed_at, token_count)
                VALUES
                    (:id, :conv_id, :user_id, 'assistant', :content, :status, :rich_type, :rich_data,
                     :error_detail, :now, :now, :now, :token_count)
            """), {
                "id": message_id,
                "conv_id": conversation_id,
                "user_id": user_id,
                "content": content,
                "status": "error" if error_detail else "complete",
                "rich_type": rich_type or None,
                "rich_data": json.dumps(rich_data) if rich_data else None,
                "error_detail": error_detail,
                "now": now,
                "token_count": len(content or ""),
            })

            session.execute(text("""
                UPDATE nex_conversations
                SET updated_at = :now,
                    message_count = message_count + 1
                WHERE id = :conv_id
            """), {
                "now": now,
                "conv_id": conversation_id,
            })
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save assistant message: {e}")
            raise
        finally:
            session.close()

    def list_conversations(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """List conversations for a user, newest first. Account-isolated."""
        session = self._get_session()
        try:
            rows = session.execute(text("""
                SELECT id, title, created_at, updated_at, model_used, message_count
                FROM nex_conversations
                WHERE user_id = :user_id AND is_deleted = 0
                ORDER BY updated_at DESC
                LIMIT :limit OFFSET :offset
            """), {"user_id": user_id, "limit": limit, "offset": offset}).fetchall()

            return [
                {
                    "id": r[0], "title": r[1],
                    "created_at": str(r[2]) if r[2] else "",
                    "updated_at": str(r[3]) if r[3] else "",
                    "model_used": r[4] or "", "message_count": r[5] or 0,
                }
                for r in rows
            ]
        finally:
            session.close()

    def get_conversation_messages(self, conversation_id: str, user_id: str) -> Optional[List[Dict]]:
        """
        Get messages for a conversation. Returns None if conversation
        doesn't exist or user doesn't own it (403).
        """
        session = self._get_session()
        try:
            # Ownership check
            owner = session.execute(text("""
                SELECT user_id FROM nex_conversations
                WHERE id = :id AND is_deleted = 0
            """), {"id": conversation_id}).fetchone()

            if not owner:
                return None
            if owner[0] != user_id:
                return None  # Forbidden

            rows = session.execute(text("""
                SELECT id, role, content, status, rich_type, rich_data,
                       tool_calls, error_detail, created_at, completed_at
                FROM nex_messages
                WHERE conversation_id = :conv_id
                ORDER BY created_at ASC
            """), {"conv_id": conversation_id}).fetchall()

            return [
                {
                    "id": r[0], "role": r[1], "content": r[2],
                    "status": r[3], "rich_type": r[4], "rich_data": r[5],
                    "tool_calls": json.loads(r[6]) if r[6] else [],
                    "error_detail": r[7],
                    "created_at": str(r[8]) if r[8] else "",
                    "completed_at": str(r[9]) if r[9] else None,
                }
                for r in rows
            ]
        finally:
            session.close()

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Soft-delete a conversation. Returns False if not owned by user."""
        session = self._get_session()
        try:
            result = session.execute(text("""
                UPDATE nex_conversations
                SET is_deleted = 1, deleted_at = :now
                WHERE id = :id AND user_id = :user_id AND is_deleted = 0
            """), {
                "id": conversation_id,
                "user_id": user_id,
                "now": datetime.now(timezone.utc),
            })
            session.commit()
            return result.rowcount > 0
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def cleanup_stale_streams(self) -> int:
        """
        On startup, mark any 'streaming' messages as 'error' —
        they were interrupted by a server crash.
        """
        session = self._get_session()
        try:
            result = session.execute(text("""
                UPDATE nex_messages
                SET status = 'error', error_detail = 'Server restarted during streaming',
                    updated_at = :now
                WHERE status = 'streaming'
            """), {"now": datetime.now(timezone.utc)})
            session.commit()
            count = result.rowcount
            if count > 0:
                logger.info(f"Cleaned up {count} stale streaming messages")
            return count
        except Exception as e:
            session.rollback()
            logger.warning(f"Stale stream cleanup failed: {e}")
            return 0
        finally:
            session.close()
