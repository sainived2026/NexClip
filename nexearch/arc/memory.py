"""
Arc Agent — Persistent Memory System
========================================
Mirrors Nex Agent's memory architecture but stores in arc_agent_memory/.
Tracks conversations, decisions, pipeline executions, evolution cycles,
client interactions, and alerts.

Storage layout:
    arc_agent_memory/
    ├── conversations/       # Chat history by session
    ├── decisions/           # Decision log with reasoning
    ├── pipeline_runs/       # Pipeline execution history
    ├── evolution_cycles/    # Evolution audit trail
    ├── client_interactions/ # Per-client interaction log
    ├── alerts/              # Alert history
    └── system_snapshots/    # Health snapshots
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArcMemory:
    """
    Persistent memory for Arc Agent across sessions.
    JSON-file-based storage with in-memory caching.
    """

    def __init__(self, memory_path: Optional[str] = None) -> None:
        default_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "arc_agent_memory"
        )
        self.root = Path(memory_path or os.environ.get("ARC_AGENT_MEMORY_PATH", default_path))
        self._subdirs = [
            "conversations", "decisions", "pipeline_runs",
            "evolution_cycles", "client_interactions", "alerts",
            "system_snapshots",
        ]
        self._ensure_dirs()

        # In-memory caches
        self._conversation_cache: List[Dict[str, Any]] = []
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._load_current_session()

    def _ensure_dirs(self) -> None:
        for sub in self._subdirs:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # ── Conversations ───────────────────────────────────────────

    def save_message(self, role: str, content: str,
                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save a chat message to current session."""
        message = {
            "id": str(uuid.uuid4())[:8],
            "role": role,
            "content": content,
            "timestamp": _utcnow(),
            "metadata": metadata or {},
        }
        self._conversation_cache.append(message)
        self._persist_session()
        return message

    def get_conversation_history(self, limit: int = 50,
                                  session_id: Optional[str] = None) -> List[Dict[str, Any]]:
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
        """Search across all sessions for relevant messages."""
        query_lower = query.lower()
        results = []
        conv_dir = self.root / "conversations"
        for f in sorted(conv_dir.glob("*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    messages = json.load(fp)
                for msg in messages:
                    if query_lower in msg.get("content", "").lower():
                        msg["session_id"] = f.stem
                        results.append(msg)
                        if len(results) >= limit:
                            return results
            except Exception:
                continue
        return results

    def get_session_list(self, limit: int = 20) -> List[Dict[str, Any]]:
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

    def save_decision(self, decision_type: str, description: str,
                       reasoning: str, alternatives: List[str],
                       outcome: str, context: Optional[Dict] = None) -> None:
        record = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": _utcnow(),
            "type": decision_type,
            "description": description,
            "reasoning": reasoning,
            "alternatives": alternatives,
            "outcome": outcome,
            "context": context or {},
        }
        self._append_to_file("decisions", f"decisions_{self._session_id}.json", record)

    def get_recent_decisions(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._read_recent_records("decisions", limit)

    # ── Pipeline Runs ──────────────────────────────────────────

    def save_pipeline_run(self, client_id: str, platform: str,
                           stages_completed: List[str],
                           results: Dict[str, Any],
                           duration_seconds: float) -> str:
        run_id = str(uuid.uuid4())[:12]
        record = {
            "run_id": run_id,
            "client_id": client_id,
            "platform": platform,
            "stages_completed": stages_completed,
            "results_summary": {k: str(v)[:200] for k, v in results.items()},
            "duration_seconds": duration_seconds,
            "timestamp": _utcnow(),
        }
        self._append_to_file("pipeline_runs", f"runs_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json", record)
        return run_id

    def get_recent_pipeline_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._read_recent_records("pipeline_runs", limit)

    # ── Evolution Cycles ───────────────────────────────────────

    def save_evolution_cycle(self, client_id: str, platform: str,
                              mode: str, changes: Dict[str, Any]) -> None:
        record = {
            "id": str(uuid.uuid4())[:8],
            "client_id": client_id,
            "platform": platform,
            "mode": mode,
            "changes_summary": str(changes)[:500],
            "timestamp": _utcnow(),
        }
        self._append_to_file("evolution_cycles", f"evolution_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json", record)

    def get_recent_evolution_cycles(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._read_recent_records("evolution_cycles", limit)

    # ── Client Interactions ────────────────────────────────────

    def save_client_interaction(self, client_id: str, action: str,
                                 details: Dict[str, Any]) -> None:
        record = {
            "client_id": client_id,
            "action": action,
            "details": details,
            "timestamp": _utcnow(),
        }
        self._append_to_file("client_interactions", f"client_{client_id}.json", record)

    # ── Alerts ─────────────────────────────────────────────────

    def save_alert(self, severity: str, source: str, message: str,
                    resolved: bool = False) -> str:
        alert_id = str(uuid.uuid4())[:8]
        record = {
            "id": alert_id,
            "timestamp": _utcnow(),
            "severity": severity,
            "source": source,
            "message": message,
            "resolved": resolved,
        }
        self._append_to_file("alerts", f"alerts_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json", record)
        return alert_id

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        all_alerts = self._read_recent_records("alerts", 100)
        return [a for a in all_alerts if not a.get("resolved", False)]

    # ── System Snapshots ───────────────────────────────────────

    def save_snapshot(self, snapshot: Dict[str, Any]) -> None:
        snapshot["timestamp"] = _utcnow()
        self._append_to_file("system_snapshots", f"snapshots_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json", snapshot)

    # ── Memory Context for LLM ─────────────────────────────────

    def get_memory_context(self, query: str = "") -> str:
        """Build memory context string for conversation engine."""
        parts = []

        recent = self._conversation_cache[-5:]
        if recent:
            parts.append("**Recent conversation:**")
            for msg in recent:
                role = "Arc" if msg["role"] == "arc" else "User"
                parts.append(f"- {role}: {msg['content'][:120]}...")

        alerts = self.get_active_alerts()
        if alerts:
            parts.append(f"\n**Active alerts ({len(alerts)}):**")
            for a in alerts[:3]:
                parts.append(f"- [{a['severity'].upper()}] {a['message']}")

        decisions = self.get_recent_decisions(3)
        if decisions:
            parts.append(f"\n**Recent decisions:**")
            for d in decisions:
                parts.append(f"- {d['description']}: {d['outcome']}")

        runs = self.get_recent_pipeline_runs(3)
        if runs:
            parts.append(f"\n**Recent pipeline runs:**")
            for r in runs:
                parts.append(f"- {r['client_id']}/{r['platform']}: {', '.join(r['stages_completed'])}")

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
        path = self.root / "conversations" / f"{self._session_id}.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._conversation_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to persist session: {e}")

    def _load_current_session(self) -> None:
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
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    def _read_recent_records(self, subdir: str, limit: int) -> List[Dict[str, Any]]:
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
