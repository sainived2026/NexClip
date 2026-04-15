"""
Nex Agent — Activity Logger
================================
Enterprise-grade persistent activity logging system.
Logs every tool call, decision, agent-to-agent message,
upload attempt, and admin interaction to disk.

All logs stored in: nex_agent_memory/activity_log/
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# ── Constants ──────────────────────────────────────────────────

_MEMORY_ROOT = Path(__file__).resolve().parent / "nex_agent_memory"
_ACTIVITY_DIR = _MEMORY_ROOT / "activity_log"
_TOOL_LOG = _ACTIVITY_DIR / "tool_calls.jsonl"
_AGENT_LOG = _ACTIVITY_DIR / "agent_messages.jsonl"
_DECISION_LOG = _ACTIVITY_DIR / "decisions.jsonl"
_UPLOAD_LOG = _ACTIVITY_DIR / "uploads.jsonl"
_ADMIN_LOG = _ACTIVITY_DIR / "admin_interactions.jsonl"
_ERROR_LOG = _ACTIVITY_DIR / "errors.jsonl"
_DAILY_DIR = _ACTIVITY_DIR / "daily"


def _ensure_dirs():
    """Create all required directories."""
    _ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
    _DAILY_DIR.mkdir(parents=True, exist_ok=True)


def _write_entry(filepath: Path, entry: Dict[str, Any]):
    """Append a JSON entry to a JSONL file."""
    _ensure_dirs()
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    # Also write to daily log
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_file = _DAILY_DIR / f"{today}.jsonl"
    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _read_entries(filepath: Path, limit: int = 100, offset: int = 0) -> List[Dict]:
    """Read entries from a JSONL file, newest first."""
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries[offset:offset + limit]


# ══════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════

def log_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    result: Any = None,
    duration_ms: float = 0,
    success: bool = True,
    error: str = "",
):
    """Log a tool invocation."""
    entry = {
        "id": str(uuid.uuid4())[:12],
        "type": "tool_call",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "arguments": arguments,
        "result_summary": str(result)[:500] if result else None,
        "duration_ms": round(duration_ms, 2),
        "success": success,
        "error": error,
    }
    _write_entry(_TOOL_LOG, entry)
    if not success:
        _write_entry(_ERROR_LOG, entry)


def log_agent_message(
    direction: str,  # "nex_to_arc" | "arc_to_nex" | "admin_to_nex" | "nex_to_admin"
    message: str,
    response: str = "",
    context: Dict[str, Any] = None,
):
    """Log an agent-to-agent or admin-to-agent message."""
    entry = {
        "id": str(uuid.uuid4())[:12],
        "type": "agent_message",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "direction": direction,
        "message": message[:2000],
        "response": response[:2000] if response else None,
        "context": context,
    }
    target = _ADMIN_LOG if "admin" in direction else _AGENT_LOG
    _write_entry(target, entry)


def log_decision(
    decision: str,
    reasoning: str,
    alternatives: List[str] = None,
    outcome: str = "",
    context: Dict[str, Any] = None,
):
    """Log a decision made by the agent."""
    entry = {
        "id": str(uuid.uuid4())[:12],
        "type": "decision",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "reasoning": reasoning,
        "alternatives": alternatives or [],
        "outcome": outcome,
        "context": context,
    }
    _write_entry(_DECISION_LOG, entry)


def log_upload(
    project_name: str,
    client_id: str,
    platform: str,
    method: str,
    clips: List[str],
    success: bool,
    error: str = "",
    details: Dict[str, Any] = None,
):
    """Log an upload attempt."""
    entry = {
        "id": str(uuid.uuid4())[:12],
        "type": "upload",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "client_id": client_id,
        "platform": platform,
        "method": method,
        "clip_count": len(clips),
        "clips": clips,
        "success": success,
        "error": error,
        "details": details,
    }
    _write_entry(_UPLOAD_LOG, entry)


def log_error(
    error_type: str,
    message: str,
    context: Dict[str, Any] = None,
    traceback_str: str = "",
):
    """Log an error event."""
    entry = {
        "id": str(uuid.uuid4())[:12],
        "type": "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": error_type,
        "message": message,
        "context": context,
        "traceback": traceback_str[:2000] if traceback_str else None,
    }
    _write_entry(_ERROR_LOG, entry)


# ── Query API ──────────────────────────────────────────────────

def get_tool_calls(limit: int = 50) -> List[Dict]:
    """Get recent tool calls."""
    return _read_entries(_TOOL_LOG, limit)


def get_agent_messages(limit: int = 50) -> List[Dict]:
    """Get recent agent-to-agent messages."""
    return _read_entries(_AGENT_LOG, limit)


def get_decisions(limit: int = 50) -> List[Dict]:
    """Get recent decisions."""
    return _read_entries(_DECISION_LOG, limit)


def get_uploads(limit: int = 50) -> List[Dict]:
    """Get recent upload attempts."""
    return _read_entries(_UPLOAD_LOG, limit)


def get_admin_interactions(limit: int = 50) -> List[Dict]:
    """Get recent admin interactions."""
    return _read_entries(_ADMIN_LOG, limit)


def get_errors(limit: int = 50) -> List[Dict]:
    """Get recent errors."""
    return _read_entries(_ERROR_LOG, limit)


def get_daily_log(date: str = "") -> List[Dict]:
    """Get all activity for a specific date (YYYY-MM-DD)."""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_file = _DAILY_DIR / f"{date}.jsonl"
    return _read_entries(daily_file, limit=1000)


def get_activity_summary() -> Dict[str, Any]:
    """Get a summary of all activity."""
    return {
        "tool_calls": len(_read_entries(_TOOL_LOG, limit=10000)),
        "agent_messages": len(_read_entries(_AGENT_LOG, limit=10000)),
        "decisions": len(_read_entries(_DECISION_LOG, limit=10000)),
        "uploads": len(_read_entries(_UPLOAD_LOG, limit=10000)),
        "admin_interactions": len(_read_entries(_ADMIN_LOG, limit=10000)),
        "errors": len(_read_entries(_ERROR_LOG, limit=10000)),
        "log_directory": str(_ACTIVITY_DIR),
    }


# ── Admin Feedback Storage ─────────────────────────────────────

_ADMIN_FEEDBACK = _MEMORY_ROOT / "admin_feedback.json"
_LEARNINGS = _MEMORY_ROOT / "learnings.json"


def store_admin_feedback(feedback: str, context: str = "", category: str = "general"):
    """Store admin feedback for self-evolution."""
    _ensure_dirs()
    data = []
    if _ADMIN_FEEDBACK.exists():
        with open(_ADMIN_FEEDBACK, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.append({
        "id": str(uuid.uuid4())[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feedback": feedback,
        "context": context,
        "category": category,
        "applied": False,
    })

    with open(_ADMIN_FEEDBACK, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def store_learning(learning: str, source: str = "", category: str = ""):
    """Store a learning for self-evolution."""
    _ensure_dirs()
    data = []
    if _LEARNINGS.exists():
        with open(_LEARNINGS, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.append({
        "id": str(uuid.uuid4())[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "learning": learning,
        "source": source,
        "category": category,
    })

    with open(_LEARNINGS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_admin_feedback(limit: int = 50) -> List[Dict]:
    """Get stored admin feedback."""
    if not _ADMIN_FEEDBACK.exists():
        return []
    with open(_ADMIN_FEEDBACK, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[-limit:]


def get_learnings(limit: int = 50) -> List[Dict]:
    """Get stored learnings."""
    if not _LEARNINGS.exists():
        return []
    with open(_LEARNINGS, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[-limit:]
