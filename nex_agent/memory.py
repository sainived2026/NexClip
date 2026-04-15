"""
Nex Agent — Persistent Memory System
========================================
Stores all conversations, decisions, agent interactions,
system snapshots, and alerts in a JSON-file-based memory.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger("nex_agent.memory")

DEFAULT_MEMORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nex_agent_memory")


class NexMemory:
    """
    Persistent memory across sessions.

    Storage layout:
        nex_agent_memory/
        ├── conversations/      # Full chat history by session
        ├── decisions/          # Decision log with reasoning
        ├── system_snapshots/   # Periodic health snapshots
        ├── agent_interactions/ # Inter-agent message log
        ├── alerts/             # Alert history
        └── knowledge_updates/  # Codebase change log
    """

    def __init__(self, memory_path: Optional[str] = None) -> None:
        self.root = Path(memory_path or os.environ.get("NEX_AGENT_MEMORY_PATH", DEFAULT_MEMORY_PATH))
        self._subdirs = [
            "conversations", "decisions", "system_snapshots",
            "agent_interactions", "alerts", "knowledge_updates",
        ]
        self._ensure_dirs()

        # In-memory caches for fast access
        self._conversation_cache: List[Dict[str, Any]] = []
        self._session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Load current session or start fresh
        self._load_current_session()

    def _ensure_dirs(self) -> None:
        for sub in self._subdirs:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # ── Conversations ───────────────────────────────────────────

    def save_message(
        self,
        role: str,  # "user" or "nex"
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save a chat message to current session."""
        message = {
            "id": str(uuid.uuid4())[:8],
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }
        self._conversation_cache.append(message)
        self._persist_session()
        return message

    def get_conversation_history(
        self, limit: int = 50, session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent conversation messages."""
        if session_id and session_id != self._session_id:
            return self._load_session(session_id)[-limit:]
        return self._conversation_cache[-limit:]

    def get_context_window(self, max_messages: int = 20) -> List[Dict[str, str]]:
        """Get recent messages formatted for LLM context."""
        recent = self._conversation_cache[-max_messages:]
        return [
            {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
            for m in recent
        ]

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search across all conversation sessions for relevant messages."""
        query_lower = query.lower()
        results = []

        conv_dir = self.root / "conversations"
        for session_file in sorted(conv_dir.glob("*.json"), reverse=True):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    messages = json.load(f)
                for msg in messages:
                    if query_lower in msg.get("content", "").lower():
                        msg["session_id"] = session_file.stem
                        results.append(msg)
                        if len(results) >= limit:
                            return results
            except Exception:
                continue

        return results

    def get_session_list(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent sessions with summary."""
        conv_dir = self.root / "conversations"
        sessions = []
        for f in sorted(conv_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    msgs = json.load(fp)
                sessions.append({
                    "session_id": f.stem,
                    "message_count": len(msgs),
                    "first_message": msgs[0]["content"][:100] if msgs else "",
                    "timestamp": msgs[0]["timestamp"] if msgs else "",
                })
            except Exception:
                continue
        return sessions

    # ── Decisions ───────────────────────────────────────────────

    def save_decision(
        self,
        decision_type: str,
        description: str,
        reasoning: str,
        alternatives: List[str],
        outcome: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log a significant decision with full reasoning."""
        record = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.utcnow().isoformat(),
            "type": decision_type,
            "description": description,
            "reasoning": reasoning,
            "alternatives": alternatives,
            "outcome": outcome,
            "context": context or {},
        }
        self._append_to_file("decisions", f"decisions_{self._session_id}.json", record)

    def get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent decision records."""
        return self._read_recent_records("decisions", limit)

    # ── System Snapshots ────────────────────────────────────────

    def save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Save a periodic system health snapshot."""
        snapshot["timestamp"] = datetime.utcnow().isoformat()
        self._append_to_file(
            "system_snapshots",
            f"snapshots_{datetime.utcnow().strftime('%Y%m%d')}.json",
            snapshot,
        )

    def get_recent_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._read_recent_records("system_snapshots", limit)

    # ── Agent Interactions ──────────────────────────────────────

    def save_agent_interaction(self, message: Dict[str, Any]) -> None:
        """Log an inter-agent message."""
        message["logged_at"] = datetime.utcnow().isoformat()
        self._append_to_file(
            "agent_interactions",
            f"interactions_{datetime.utcnow().strftime('%Y%m%d')}.json",
            message,
        )

    def get_recent_interactions(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._read_recent_records("agent_interactions", limit)

    # ── Alerts ──────────────────────────────────────────────────

    def save_alert(
        self,
        severity: str,
        source: str,
        message: str,
        resolved: bool = False,
        resolution: str = "",
    ) -> str:
        """Log an alert with resolution tracking."""
        alert_id = str(uuid.uuid4())[:8]
        record = {
            "id": alert_id,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "source": source,
            "message": message,
            "resolved": resolved,
            "resolution": resolution,
        }
        self._append_to_file("alerts", f"alerts_{datetime.utcnow().strftime('%Y%m%d')}.json", record)
        return alert_id

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get unresolved alerts."""
        all_alerts = self._read_recent_records("alerts", 100)
        return [a for a in all_alerts if not a.get("resolved", False)]

    def resolve_alert(self, alert_id: str, resolution: str) -> None:
        """Mark an alert as resolved."""
        # Read all alert files, find and update
        alerts_dir = self.root / "alerts"
        for f in alerts_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    records = json.load(fp)
                updated = False
                for r in records:
                    if r.get("id") == alert_id:
                        r["resolved"] = True
                        r["resolution"] = resolution
                        r["resolved_at"] = datetime.utcnow().isoformat()
                        updated = True
                if updated:
                    with open(f, "w", encoding="utf-8") as fp:
                        json.dump(records, fp, indent=2)
                    return
            except Exception:
                continue

    # ── Knowledge Updates ───────────────────────────────────────

    def save_knowledge_update(self, update: Dict[str, Any]) -> None:
        """Log a codebase change or index update."""
        update["timestamp"] = datetime.utcnow().isoformat()
        self._append_to_file(
            "knowledge_updates",
            f"updates_{datetime.utcnow().strftime('%Y%m%d')}.json",
            update,
        )

    # ── Memory Summary for Context ──────────────────────────────

    def get_memory_context(self, query: str = "") -> str:
        """Build a memory context string for the conversation engine."""
        parts = []

        # Recent conversation summary
        recent = self._conversation_cache[-5:]
        if recent:
            parts.append("**Recent conversation:**")
            for msg in recent:
                role = "You" if msg["role"] == "nex" else "Admin"
                parts.append(f"- {role}: {msg['content'][:120]}...")

        # Active alerts
        alerts = self.get_active_alerts()
        if alerts:
            parts.append(f"\n**Active alerts ({len(alerts)}):**")
            for a in alerts[:3]:
                parts.append(f"- [{a['severity'].upper()}] {a['message']}")

        # Recent decisions
        decisions = self.get_recent_decisions(3)
        if decisions:
            parts.append(f"\n**Recent decisions:**")
            for d in decisions:
                parts.append(f"- {d['description']}: {d['outcome']}")

        # Search for relevant past context
        if query:
            past = self.search_conversations(query, limit=3)
            if past:
                parts.append(f"\n**Related past conversation:**")
                for p in past:
                    if p.get("session_id") != self._session_id:
                        parts.append(f"- (session {p['session_id']}): {p['content'][:80]}…")

        return "\n".join(parts) if parts else "No prior conversation history."

    # ── Internal Helpers ────────────────────────────────────────

    def _persist_session(self) -> None:
        """Write current conversation to disk."""
        path = self.root / "conversations" / f"{self._session_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._conversation_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to persist session: {e}")

    def _load_current_session(self) -> None:
        """Load existing session if file exists."""
        path = self.root / "conversations" / f"{self._session_id}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._conversation_cache = json.load(f)
            except Exception:
                self._conversation_cache = []

    def _load_session(self, session_id: str) -> List[Dict[str, Any]]:
        path = self.root / "conversations" / f"{session_id}.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _append_to_file(self, subdir: str, filename: str, record: Dict[str, Any]) -> None:
        """Append a record to a JSON array file."""
        path = self.root / subdir / filename
        records = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        records.append(record)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def _read_recent_records(self, subdir: str, limit: int) -> List[Dict[str, Any]]:
        """Read recent records from a subdir, reverse chronological."""
        records = []
        subdir_path = self.root / subdir
        for f in sorted(subdir_path.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, list):
                    records.extend(reversed(data))
                if len(records) >= limit:
                    break
            except Exception:
                continue
        return records[:limit]
