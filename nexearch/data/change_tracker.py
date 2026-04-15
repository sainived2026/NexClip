"""
Nexearch — Change Tracker
Full audit trail of every modification Nexearch makes.
Supports revert with negative feedback to Arc Agent.

Tracked changes:
- System prompt modifications (per client)
- DNA updates (per client per platform)
- Evolution cycles
- Directive changes
- Style overrides
- Writing profile updates
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from nexearch.config import get_nexearch_settings


def _utcnow_str():
    return datetime.now(timezone.utc).isoformat()


class ChangeTracker:
    """
    Tracks every modification Nexearch makes per client.
    Each change is stored with a full before/after snapshot for revert.
    """

    CHANGE_TYPES = [
        "system_prompt", "dna_update", "evolution",
        "directive", "style_override", "writing_profile",
    ]

    def __init__(self, client_id: str):
        settings = get_nexearch_settings()
        self._base_dir = (Path(settings.NEXEARCH_CLIENTS_DIR).resolve() /
                          "clients" / client_id / "_changes")
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._client_id = client_id
        self._index_path = self._base_dir / "change_index.json"

        if not self._index_path.exists():
            self._save_json(self._index_path, {"changes": [], "reverted": []})

    def record_change(self, change_type: str, platform: str,
                       description: str, before_state: Any,
                       after_state: Any, metadata: Dict = None) -> str:
        """Record a change with full before/after snapshot."""
        change_id = f"chg_{uuid.uuid4().hex[:8]}"

        change = {
            "change_id": change_id,
            "change_type": change_type,
            "platform": platform,
            "client_id": self._client_id,
            "description": description,
            "timestamp": _utcnow_str(),
            "reverted": False,
            "reverted_at": None,
            "revert_reason": None,
            "metadata": metadata or {},
        }

        # Save the full change with before/after
        detail_path = self._base_dir / f"{change_id}.json"
        self._save_json(detail_path, {
            **change,
            "before_state": before_state,
            "after_state": after_state,
        })

        # Update index
        index = self._load_json(self._index_path) or {"changes": [], "reverted": []}
        index["changes"].append(change)
        self._save_json(self._index_path, index)

        logger.info(f"[ChangeTracker] Recorded {change_type} change: {change_id}")
        return change_id

    def get_history(self, change_type: str = "all",
                     limit: int = 20) -> List[Dict]:
        """Get change history, optionally filtered by type."""
        index = self._load_json(self._index_path) or {"changes": []}
        changes = index["changes"]

        if change_type != "all":
            changes = [c for c in changes if c["change_type"] == change_type]

        return changes[-limit:]

    def get_change_detail(self, change_id: str) -> Optional[Dict]:
        """Get full change detail including before/after states."""
        path = self._base_dir / f"{change_id}.json"
        return self._load_json(path)

    def revert_change(self, change_id: str, reason: str = "") -> Dict:
        """
        Revert a specific change by restoring the before_state.
        This also sends negative feedback to the evolution engine.
        """
        detail = self.get_change_detail(change_id)
        if not detail:
            return {"success": False, "error": f"Change {change_id} not found"}

        if detail.get("reverted"):
            return {"success": False, "error": "Already reverted"}

        change_type = detail["change_type"]
        platform = detail["platform"]
        before_state = detail.get("before_state")

        # Restore the before_state to the appropriate store
        restored = False
        try:
            if change_type == "system_prompt":
                from nexearch.data.nexclip_client_store import NexClipClientStore
                store = NexClipClientStore(self._client_id)
                if before_state:
                    store.save_prompt_injection(
                        before_state.get("prompt", ""),
                        metadata={"reverted_from": change_id, "reason": reason},
                    )
                restored = True

            elif change_type == "dna_update":
                from nexearch.data.client_store import ClientDataStore
                store = ClientDataStore(self._client_id)
                if before_state:
                    store.save_platform_dna(platform, before_state,
                                            version=before_state.get("version", 0))
                restored = True

            elif change_type == "directive":
                from nexearch.data.client_store import ClientDataStore
                store = ClientDataStore(self._client_id)
                if before_state:
                    store.save_directive(platform, f"reverted_{change_id}",
                                         before_state)
                restored = True

            elif change_type == "style_override":
                from nexearch.data.nexclip_client_store import NexClipClientStore
                store = NexClipClientStore(self._client_id)
                # Record the revert as a new adjustment
                store.save_style_adjustment(
                    f"revert_{change_id}",
                    {"type": "revert", "original_change": change_id,
                     "restored_state": before_state},
                )
                restored = True

            elif change_type == "writing_profile":
                from nexearch.data.nexclip_client_store import NexClipClientStore
                store = NexClipClientStore(self._client_id)
                if before_state:
                    store.save_writing_profile(platform, before_state)
                restored = True

            else:
                # evolution and other types — record as negative feedback
                restored = True

        except Exception as e:
            return {"success": False, "error": f"Revert failed: {e}"}

        # Mark as reverted in the detail file
        detail["reverted"] = True
        detail["reverted_at"] = _utcnow_str()
        detail["revert_reason"] = reason
        self._save_json(self._base_dir / f"{change_id}.json", detail)

        # Update index
        index = self._load_json(self._index_path) or {"changes": [], "reverted": []}
        for c in index["changes"]:
            if c["change_id"] == change_id:
                c["reverted"] = True
                c["reverted_at"] = _utcnow_str()
                c["revert_reason"] = reason
        index["reverted"].append(change_id)
        self._save_json(self._index_path, index)

        # Record this revert as negative feedback for evolution
        self._record_negative_feedback(change_id, change_type, reason)

        logger.info(f"[ChangeTracker] Reverted change {change_id}: {reason}")
        return {
            "success": True,
            "change_id": change_id,
            "change_type": change_type,
            "restored": restored,
            "feedback_sent": True,
        }

    def _record_negative_feedback(self, change_id: str, change_type: str,
                                    reason: str):
        """Send negative feedback to the evolution engine."""
        feedback_path = self._base_dir / "negative_feedback.json"
        feedback = self._load_json(feedback_path) or {"feedback": []}
        feedback["feedback"].append({
            "change_id": change_id,
            "change_type": change_type,
            "reason": reason,
            "timestamp": _utcnow_str(),
            "processed": False,
        })
        self._save_json(feedback_path, feedback)

    def get_negative_feedback(self, unprocessed_only: bool = True) -> List[Dict]:
        """Get negative feedback entries (for evolution engine to consume)."""
        feedback = self._load_json(self._base_dir / "negative_feedback.json")
        if not feedback:
            return []
        entries = feedback.get("feedback", [])
        if unprocessed_only:
            entries = [f for f in entries if not f.get("processed")]
        return entries

    def mark_feedback_processed(self, change_id: str):
        """Mark negative feedback as processed by evolution."""
        feedback_path = self._base_dir / "negative_feedback.json"
        feedback = self._load_json(feedback_path) or {"feedback": []}
        for f in feedback["feedback"]:
            if f["change_id"] == change_id:
                f["processed"] = True
        self._save_json(feedback_path, feedback)

    def _save_json(self, path: Path, data: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _load_json(self, path: Path) -> Optional[Dict]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
