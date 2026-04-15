"""
Nex Agent — Rich Response Types
==================================
Generators for all 8 structured response types that
the frontend renders as interactive cards.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger("nex_agent.rich_responses")


class ResponseType:
    TEXT = "text"
    STATUS_CARD = "status_card"
    QUALITY_CHART = "quality_chart"
    AGENT_FEED = "agent_feed"
    FILE_REFERENCE = "file_reference"
    ACTION_CONFIRMATION = "action_confirmation"
    ALERT_CARD = "alert_card"
    PATCH_SUMMARY = "patch_summary"


def text_response(content: str) -> Dict[str, Any]:
    """Standard markdown text response."""
    return {
        "type": ResponseType.TEXT,
        "content": content,
    }


def status_card(
    backend: bool,
    frontend: bool,
    last_score: float,
    db_projects: int,
    db_clips: int,
    issues: List[str],
) -> Dict[str, Any]:
    """System health status card."""
    return {
        "type": ResponseType.STATUS_CARD,
        "data": {
            "backend": {"healthy": backend, "label": "Backend API"},
            "frontend": {"healthy": frontend, "label": "Frontend"},
            "database": {"projects": db_projects, "clips": db_clips, "label": "Database"},
            "last_score": last_score,
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def quality_chart(
    data_points: List[Dict[str, Any]],
    title: str = "Quality Score Trend",
) -> Dict[str, Any]:
    """Quality trend chart data for frontend rendering."""
    return {
        "type": ResponseType.QUALITY_CHART,
        "data": {
            "title": title,
            "points": data_points,  # [{cycle, score, dimensions...}]
        },
    }


def agent_feed(
    activities: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Live agent activity feed."""
    return {
        "type": ResponseType.AGENT_FEED,
        "data": {
            "activities": activities,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def file_reference(
    file_path: str,
    purpose: str,
    code_snippet: str = "",
    line_start: int = 0,
    line_end: int = 0,
    language: str = "python",
    functions: Optional[List[str]] = None,
    classes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Code file reference with snippet."""
    return {
        "type": ResponseType.FILE_REFERENCE,
        "data": {
            "file_path": file_path,
            "purpose": purpose,
            "code_snippet": code_snippet,
            "line_start": line_start,
            "line_end": line_end,
            "language": language,
            "functions": functions or [],
            "classes": classes or [],
        },
    }


def action_confirmation(
    action: str,
    description: str,
    severity: str = "normal",
    requires_approval: bool = True,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Action confirmation card with Approve/Cancel buttons."""
    return {
        "type": ResponseType.ACTION_CONFIRMATION,
        "data": {
            "action": action,
            "description": description,
            "severity": severity,
            "requires_approval": requires_approval,
            "params": params or {},
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def alert_card(
    severity: str,
    title: str,
    message: str,
    source: str,
    suggested_actions: Optional[List[str]] = None,
    auto_resolved: bool = False,
) -> Dict[str, Any]:
    """Color-coded alert card with severity and action buttons."""
    return {
        "type": ResponseType.ALERT_CARD,
        "data": {
            "severity": severity,
            "title": title,
            "message": message,
            "source": source,
            "suggested_actions": suggested_actions or [],
            "auto_resolved": auto_resolved,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def patch_summary(
    patches: List[Dict[str, Any]],
    total_improvement: float = 0.0,
) -> Dict[str, Any]:
    """Expandable patch list with before/after scores."""
    return {
        "type": ResponseType.PATCH_SUMMARY,
        "data": {
            "patches": patches,
            "total_improvement": total_improvement,
            "patch_count": len(patches),
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
