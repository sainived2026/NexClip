"""
Nex Agent Tools — Database & Storage (Category 4)
=====================================================
Read-only SQL queries, clip listing, system stats, storage inspection.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.database")

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
DB_PATH = os.path.join(PROJECT_ROOT, "backend", "nexclip.db")
STORAGE_PATH = os.path.join(PROJECT_ROOT, "backend", "storage")


def _db_query(sql: str, params: str = "[]") -> Dict[str, Any]:
    """Execute a read-only SQL query."""
    if not os.path.exists(DB_PATH):
        return {"success": False, "error": f"Database not found at {DB_PATH}"}

    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return {"success": False, "error": "Only SELECT queries are allowed for safety"}

    try:
        parsed_params = json.loads(params) if isinstance(params, str) else params
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, parsed_params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"success": True, "rows": rows, "count": len(rows)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _db_get_clips(status: str = "", limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    if not os.path.exists(DB_PATH):
        return {"success": False, "error": "Database not found", "clips": [], "total": 0}

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT * FROM clips WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?", (status, limit, offset))
        else:
            cursor.execute("SELECT * FROM clips ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))

        clips = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM clips")
        total = cursor.fetchone()[0]
        conn.close()

        return {"success": True, "clips": clips, "total": total}
    except Exception as e:
        return {"success": False, "error": str(e), "clips": [], "total": 0}


def _db_get_system_stats() -> Dict[str, Any]:
    stats: Dict[str, Any] = {"success": True}

    if not os.path.exists(DB_PATH):
        stats["database"] = "not found"
        return stats

    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        cursor = conn.cursor()

        for table, key in [("clips", "total_clips"), ("projects", "total_projects"), ("users", "total_users")]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[key] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats[key] = 0

        # Queue depth (processing projects)
        try:
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status IN ('pending', 'processing')")
            stats["queue_depth"] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats["queue_depth"] = 0

        conn.close()
    except Exception as e:
        stats["error"] = str(e)

    # Storage size
    total_size = 0
    if os.path.isdir(STORAGE_PATH):
        for root, dirs, files in os.walk(STORAGE_PATH):
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))
    stats["storage_gb"] = round(total_size / (1024 ** 3), 2)

    return stats


def _storage_list(prefix: str = "") -> Dict[str, Any]:
    if not os.path.isdir(STORAGE_PATH):
        return {"success": False, "error": "Storage directory not found"}

    search_path = os.path.join(STORAGE_PATH, prefix) if prefix else STORAGE_PATH
    files = []
    total_size = 0

    if os.path.isdir(search_path):
        for root, dirs, filenames in os.walk(search_path):
            for f in filenames:
                fp = os.path.join(root, f)
                size = os.path.getsize(fp)
                total_size += size
                files.append({
                    "path": os.path.relpath(fp, STORAGE_PATH),
                    "size_mb": round(size / (1024 * 1024), 2),
                })
                if len(files) >= 100:
                    break
            if len(files) >= 100:
                break

    return {"success": True, "files": files, "total_size_gb": round(total_size / (1024 ** 3), 3)}


def register(executor: "ToolExecutor") -> int:
    executor.register(name="db_query", description="Execute a read-only SELECT query against the NexClip database.", category="database", handler=_db_query, parameters={"type": "object", "properties": {"sql": {"type": "string"}, "params": {"type": "string", "default": "[]"}}, "required": ["sql"]})
    executor.register(name="db_get_clips", description="Get clips from the database with optional status filter.", category="database", handler=_db_get_clips, parameters={"type": "object", "properties": {"status": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 20}, "offset": {"type": "integer", "default": 0}}, "required": []})
    executor.register(name="db_get_system_stats", description="Get aggregate system stats: total clips, projects, users, queue depth, storage size.", category="database", handler=_db_get_system_stats, parameters={"type": "object", "properties": {}})
    executor.register(name="storage_list", description="List files in the NexClip storage directory.", category="database", handler=_storage_list, parameters={"type": "object", "properties": {"prefix": {"type": "string", "default": ""}}, "required": []})
    return 4
