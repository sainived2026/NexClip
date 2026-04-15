"""
Nexearch — System Metadata & Data Aggregation
Tracks overall system status and provides cross-client data views.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from nexearch.config import get_nexearch_settings
from nexearch.data.client_store import ClientDataStore, PLATFORMS


def _utcnow_str():
    return datetime.now(timezone.utc).isoformat()


class SystemMeta:
    """
    System-level metadata and status tracking.
    Provides cross-client views and system health data.
    """

    def __init__(self):
        settings = get_nexearch_settings()
        self._base_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve() / "_meta"
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def update_system_status(self, status: Dict):
        """Update overall system status."""
        path = self._base_dir / "system_status.json"
        data = self._load_json(path) or {}
        data.update(status)
        data["last_updated"] = _utcnow_str()
        self._save_json(path, data)

    def update_last_sync(self, client_id: str, platform: str, sync_type: str):
        """Record last sync timestamp."""
        path = self._base_dir / "last_sync.json"
        data = self._load_json(path) or {"syncs": {}}
        key = f"{client_id}_{platform}_{sync_type}"
        data["syncs"][key] = _utcnow_str()
        self._save_json(path, data)

    def get_system_status(self) -> Dict:
        return self._load_json(self._base_dir / "system_status.json") or {}

    def get_all_client_summaries(self) -> List[Dict]:
        """Get summaries of all clients."""
        settings = get_nexearch_settings()
        clients_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve() / "clients"
        summaries = []

        if clients_dir.exists():
            for client_dir in clients_dir.iterdir():
                if client_dir.is_dir():
                    manifest_path = client_dir / "manifest.json"
                    if manifest_path.exists():
                        manifest = self._load_json(manifest_path)
                        if manifest:
                            summaries.append({
                                "client_id": manifest.get("client_id"),
                                "account_handle": manifest.get("account_handle"),
                                "last_updated": manifest.get("last_updated"),
                                "stats": manifest.get("stats", {}),
                                "platforms": list(manifest.get("platforms", {}).keys()),
                            })

        return summaries

    def get_client(self, client_id: str) -> Optional[Dict]:
        """Get a single client's manifest by ID."""
        settings = get_nexearch_settings()
        clients_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve() / "clients"
        manifest_path = clients_dir / client_id / "manifest.json"
        if manifest_path.exists():
            return self._load_json(manifest_path)
        return None

    def _save_json(self, path: Path, data: Dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _load_json(self, path: Path) -> Optional[Dict]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
