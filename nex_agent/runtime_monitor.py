"""
Nex Agent — Runtime Monitor
================================
Polls backend/frontend health, SIMAS status, database state,
and tails log files. Returns structured SystemSnapshot for
enriching Nex Agent conversation context.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
import urllib.request
import urllib.error

logger = logging.getLogger("nex_agent.runtime_monitor")


class SystemSnapshot:
    """Structured snapshot of system health at a point in time."""

    def __init__(self) -> None:
        self.timestamp = datetime.utcnow().isoformat()
        self.backend_healthy = False
        self.backend_response_ms = 0
        self.frontend_healthy = False
        self.frontend_healthy = False
        self.db_project_count = 0
        self.db_clip_count = 0
        self.db_error_count = 0
        self.active_issues: List[str] = []
        self.recent_logs: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "backend": {"healthy": self.backend_healthy, "response_ms": self.backend_response_ms},
            "frontend": {"healthy": self.frontend_healthy},
            "frontend": {"healthy": self.frontend_healthy},
            "database": {"projects": self.db_project_count, "clips": self.db_clip_count, "errors": self.db_error_count},
            "active_issues": self.active_issues,
        }

    def to_markdown(self) -> str:
        """Format for LLM context injection."""
        be = "✅ Healthy" if self.backend_healthy else "❌ Down"
        fe = "✅ Healthy" if self.frontend_healthy else "⚠️ Unknown"
        db = f"{self.db_project_count} projects, {self.db_clip_count} clips"
        lines = [
            f"- **Backend:** {be} ({self.backend_response_ms}ms)",
            f"- **Frontend:** {fe}",
            f"- **Database:** {db}",
        ]

        if self.active_issues:
            lines.append(f"- **Issues:** {', '.join(self.active_issues)}")

        return "\n".join(lines)


class RuntimeMonitor:
    """
    Continuously monitors NexClip system health.
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        frontend_url: str = "http://localhost:3000",
        db_path: str = "backend/nexclip.db",
    ) -> None:
        self.backend_url = backend_url
        self.frontend_url = frontend_url
        self.db_path = db_path
        self._last_snapshot: Optional[SystemSnapshot] = None

    def take_snapshot(self) -> SystemSnapshot:
        """Take a full system health snapshot."""
        snap = SystemSnapshot()

        # Backend health
        self._check_backend(snap)

        # Frontend health
        self._check_frontend(snap)



        # Database state
        self._check_database(snap)

        # Aggregate issues
        if not snap.backend_healthy:
            snap.active_issues.append("Backend API is not responding")
        if snap.db_error_count > 0:
            snap.active_issues.append(f"{snap.db_error_count} failed projects in database")

        # Read recent logs
        snap.recent_logs = self._tail_logs(5)

        self._last_snapshot = snap
        return snap

    def get_cached_snapshot(self) -> SystemSnapshot:
        """Return cached snapshot or take a new one."""
        if self._last_snapshot:
            return self._last_snapshot
        return self.take_snapshot()

    # ── Health Checks ───────────────────────────────────────────

    def _check_backend(self, snap: SystemSnapshot) -> None:
        """Poll backend /health endpoint."""
        try:
            start = time.time()
            req = urllib.request.Request(f"{self.backend_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                snap.backend_response_ms = int((time.time() - start) * 1000)
                snap.backend_healthy = resp.status == 200
        except Exception:
            snap.backend_healthy = False
            snap.backend_response_ms = -1

    def _check_frontend(self, snap: SystemSnapshot) -> None:
        """Check if frontend is responding."""
        try:
            req = urllib.request.Request(self.frontend_url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                snap.frontend_healthy = resp.status == 200
        except Exception:
            snap.frontend_healthy = False



    def _check_database(self, snap: SystemSnapshot) -> None:
        """Query SQLite database for counts."""
        if not os.path.exists(self.db_path):
            return

        try:
            conn = sqlite3.connect(self.db_path, timeout=5)
            cursor = conn.cursor()

            # Project count
            try:
                cursor.execute("SELECT COUNT(*) FROM projects")
                snap.db_project_count = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                pass

            # Clip count
            try:
                cursor.execute("SELECT COUNT(*) FROM clips")
                snap.db_clip_count = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                pass

            # Error count (failed projects)
            try:
                cursor.execute("SELECT COUNT(*) FROM projects WHERE status = 'failed'")
                snap.db_error_count = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                pass

            conn.close()
        except Exception as e:
            logger.debug(f"Database check failed: {e}")

    # ── Log Tailing ─────────────────────────────────────────────

    def _tail_logs(self, n: int = 10) -> List[str]:
        """Read last N lines from key log files."""
        log_files = [
            "backend/ai_response_debug.log",
            "backend/yt_dlp_out.txt",
        ]
        lines = []
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        all_lines = f.readlines()
                        last_n = all_lines[-n:] if len(all_lines) >= n else all_lines
                        for line in last_n:
                            stripped = line.strip()
                            if stripped:
                                lines.append(f"[{Path(log_file).name}] {stripped[:200]}")
                except Exception:
                    continue
        return lines[-n:]

    # ── Formatted Output ────────────────────────────────────────

    def get_health_markdown(self) -> str:
        """Get formatted health status for Nex Agent context."""
        snap = self.take_snapshot()
        return snap.to_markdown()



    def get_recent_activity(self, limit: int = 10) -> str:
        """Get recent activity formatted as text."""
        logs = self._tail_logs(limit)
        if logs:
            return "\n".join(f"- {l}" for l in logs)
        return "No recent activity logged."
