"""
Nexearch — Universal Data Store
Cross-client universal intelligence aggregated per platform.
Learns global patterns from ALL clients to improve individual performance.

Directory Structure:
nexearch_data/universal/
├── {platform}/
│   ├── global_patterns/
│   │   ├── winning_patterns.json       # Winning patterns across all clients
│   │   ├── avoid_patterns.json         # Patterns that consistently underperform
│   │   ├── trend_signals.json          # Current trending patterns
│   │   └── writing_benchmarks.json     # Writing quality benchmarks
│   ├── global_dna/
│   │   ├── universal_dna_v{V}.json     # Versioned universal DNA
│   │   └── current_universal_dna.json  # Active universal DNA
│   ├── global_evolution/
│   │   ├── cycle_{id}.json             # Evolution cycle data
│   │   ├── rubric_weights.json         # Global rubric weights
│   │   └── evolution_log.json          # Evolution history
│   └── benchmarks/
│       ├── engagement_benchmarks.json  # Global engagement benchmarks
│       ├── hook_effectiveness.json     # Hook type effectiveness ranking
│       └── content_category_performance.json
└── cross_platform/
    ├── global_trends.json              # Cross-platform trend analysis
    └── cross_platform_insights.json    # Universal insights
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from nexearch.config import get_nexearch_settings


PLATFORMS = ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"]


def _utcnow_str():
    return datetime.now(timezone.utc).isoformat()


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class UniversalDataStore:
    """
    Universal (cross-client) data store for global intelligence.
    Aggregates patterns, DNA, and evolution data from ALL clients.
    Operates per-platform + cross-platform.
    """

    def __init__(self):
        settings = get_nexearch_settings()
        self._base_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve() / "universal"
        self._init_directories()

    def _init_directories(self):
        """Create the universal directory tree."""
        for platform in PLATFORMS:
            for subdir in ["global_patterns", "global_dna", "global_evolution", "benchmarks"]:
                (self._base_dir / platform / subdir).mkdir(parents=True, exist_ok=True)
        (self._base_dir / "cross_platform").mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ── Global Patterns ───────────────────────────────────────

    def get_winning_patterns(self, platform: str) -> Dict:
        """Get global winning patterns for a platform."""
        path = self._base_dir / platform / "global_patterns" / "winning_patterns.json"
        return self._load_json(path) or {"patterns": [], "updated_at": "never"}

    def update_winning_patterns(self, platform: str, patterns: List[Dict],
                                  source_client_id: str):
        """Add or update winning patterns from a client's S/A-tier data."""
        path = self._base_dir / platform / "global_patterns" / "winning_patterns.json"
        existing = self._load_json(path) or {"patterns": [], "contributions": []}

        # Merge new patterns (avoid duplicates by pattern name/type)
        existing_names = {p.get("name", p.get("type", "")) for p in existing["patterns"]}
        for p in patterns:
            key = p.get("name", p.get("type", ""))
            if key and key not in existing_names:
                p["source_client"] = source_client_id
                p["discovered_at"] = _utcnow_str()
                existing["patterns"].append(p)
                existing_names.add(key)

        existing["updated_at"] = _utcnow_str()
        existing["contributions"].append({
            "client_id": source_client_id, "timestamp": _utcnow_str(),
            "patterns_added": len(patterns),
        })
        self._save_json(path, existing)

    def update_avoid_patterns(self, platform: str, patterns: List[Dict],
                                source_client_id: str):
        """Update global avoid patterns from C-tier data."""
        path = self._base_dir / platform / "global_patterns" / "avoid_patterns.json"
        existing = self._load_json(path) or {"patterns": [], "contributions": []}

        existing_names = {p.get("name", p.get("type", "")) for p in existing["patterns"]}
        for p in patterns:
            key = p.get("name", p.get("type", ""))
            if key and key not in existing_names:
                p["source_client"] = source_client_id
                p["discovered_at"] = _utcnow_str()
                existing["patterns"].append(p)

        existing["updated_at"] = _utcnow_str()
        existing["contributions"].append({
            "client_id": source_client_id, "timestamp": _utcnow_str(),
        })
        self._save_json(path, existing)

    def update_trend_signals(self, platform: str, trends: Dict):
        """Update current trending patterns for a platform."""
        path = self._base_dir / platform / "global_patterns" / "trend_signals.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "platform": platform,
                               "trends": trends})

    def update_writing_benchmarks(self, platform: str, benchmarks: Dict):
        """Update writing quality benchmarks for a platform."""
        path = self._base_dir / platform / "global_patterns" / "writing_benchmarks.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "platform": platform,
                               "benchmarks": benchmarks})

    # ── Universal DNA ─────────────────────────────────────────

    def get_universal_dna(self, platform: str) -> Optional[Dict]:
        """Get the current universal DNA for a platform."""
        path = self._base_dir / platform / "global_dna" / "current_universal_dna.json"
        return self._load_json(path)

    def save_universal_dna(self, platform: str, dna: Dict, version: int) -> str:
        """Save universal DNA with versioning."""
        # Versioned
        v_path = self._base_dir / platform / "global_dna" / f"universal_dna_v{version}.json"
        dna_data = {
            "version": version, "platform": platform,
            "generated_at": _utcnow_str(), "dna": dna,
            "contributing_clients": dna.get("_contributing_clients", []),
        }
        self._save_json(v_path, dna_data)

        # Current
        c_path = self._base_dir / platform / "global_dna" / "current_universal_dna.json"
        self._save_json(c_path, dna_data)

        logger.info(f"[UniversalStore] Universal DNA v{version} saved for {platform}")
        return str(c_path)

    # ── Universal Evolution ───────────────────────────────────

    def save_universal_evolution(self, platform: str, cycle_id: str,
                                  evolution_data: Dict) -> str:
        """Save a universal evolution cycle for a platform."""
        path = self._base_dir / platform / "global_evolution" / f"cycle_{cycle_id}.json"
        self._save_json(path, {
            "cycle_id": cycle_id, "platform": platform,
            "evolved_at": _utcnow_str(), "mode": "universal",
            "data": evolution_data,
        })

        # Append to evolution log
        self._append_log(
            self._base_dir / platform / "global_evolution" / "evolution_log.json",
            {"cycle_id": cycle_id, "timestamp": _utcnow_str(),
             "magnitude": evolution_data.get("magnitude", 0),
             "contributing_clients": evolution_data.get("contributing_clients", [])}
        )

        # Update global rubric weights
        if evolution_data.get("rubric_updates"):
            weights_path = self._base_dir / platform / "global_evolution" / "rubric_weights.json"
            existing = self._load_json(weights_path) or {"weights": {}, "history": []}
            for update in evolution_data["rubric_updates"]:
                dim = update.get("dimension", "")
                existing["weights"][dim] = update.get("new_weight", 0)
            existing["history"].append({"cycle_id": cycle_id, "timestamp": _utcnow_str()})
            self._save_json(weights_path, existing)

        return str(path)

    def get_universal_rubric_weights(self, platform: str) -> Dict:
        """Get current global rubric weights for a platform."""
        path = self._base_dir / platform / "global_evolution" / "rubric_weights.json"
        data = self._load_json(path)
        return data.get("weights", {}) if data else {}

    # ── Benchmarks ────────────────────────────────────────────

    def update_engagement_benchmarks(self, platform: str, benchmarks: Dict):
        """Update global engagement benchmarks from all clients."""
        path = self._base_dir / platform / "benchmarks" / "engagement_benchmarks.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "platform": platform,
                               "benchmarks": benchmarks})

    def update_hook_effectiveness(self, platform: str, rankings: List[Dict]):
        """Update hook type effectiveness rankings."""
        path = self._base_dir / platform / "benchmarks" / "hook_effectiveness.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "platform": platform,
                               "rankings": rankings})

    def update_category_performance(self, platform: str, performance: Dict):
        """Update content category performance data."""
        path = self._base_dir / platform / "benchmarks" / "content_category_performance.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "platform": platform,
                               "performance": performance})

    def get_engagement_benchmarks(self, platform: str) -> Optional[Dict]:
        path = self._base_dir / platform / "benchmarks" / "engagement_benchmarks.json"
        return self._load_json(path)

    # ── Cross-Platform Intelligence ───────────────────────────

    def save_global_trends(self, trends: Dict):
        """Save cross-platform global trends."""
        path = self._base_dir / "cross_platform" / "global_trends.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "trends": trends})

    def save_cross_platform_insights(self, insights: Dict):
        """Save cross-platform universal insights."""
        path = self._base_dir / "cross_platform" / "cross_platform_insights.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "insights": insights})

    def get_global_trends(self) -> Optional[Dict]:
        path = self._base_dir / "cross_platform" / "global_trends.json"
        return self._load_json(path)

    # ── Aggregation from Client Data ──────────────────────────

    def aggregate_from_client(self, platform: str, client_id: str,
                               scored_data: Dict, dna_data: Dict):
        """
        Ingest a client's scored data to update universal patterns.
        Called after each client's pipeline completes.
        """
        # Extract winning patterns from S/A-tier posts
        winning = []
        avoid = []

        if dna_data.get("winning_patterns"):
            wp = dna_data["winning_patterns"]
            for hook in wp.get("top_hook_types", []):
                winning.append({"type": "hook", "name": hook, "platform": platform})
            for topic in wp.get("top_primary_topics", []):
                winning.append({"type": "topic", "name": topic, "platform": platform})
            for cat in wp.get("top_content_categories", []):
                winning.append({"type": "category", "name": cat, "platform": platform})
            for wp_entry in wp.get("writing_patterns", []):
                winning.append({"type": "writing_pattern", "name": wp_entry, "platform": platform})

        if dna_data.get("avoid_patterns"):
            ap = dna_data["avoid_patterns"]
            for hook in ap.get("weak_hook_types", []):
                avoid.append({"type": "hook", "name": hook, "platform": platform})
            for topic in ap.get("underperforming_topics", []):
                avoid.append({"type": "topic", "name": topic, "platform": platform})

        if winning:
            self.update_winning_patterns(platform, winning, client_id)
        if avoid:
            self.update_avoid_patterns(platform, avoid, client_id)

        # Update benchmarks from scored data
        if scored_data.get("tier_distribution"):
            benchmarks = self.get_engagement_benchmarks(platform) or {"benchmarks": {}}
            benchmarks["benchmarks"][f"client_{client_id}"] = {
                "tier_distribution": scored_data["tier_distribution"],
                "updated_at": _utcnow_str(),
            }
            self.update_engagement_benchmarks(platform, benchmarks.get("benchmarks", {}))

        logger.info(f"[UniversalStore] Aggregated data from client {client_id} for {platform}")

    # ── Private Helpers ───────────────────────────────────────

    def _save_json(self, path: Path, data: Dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _load_json(self, path: Path) -> Optional[Dict]:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _append_log(self, path: Path, entry: Dict):
        existing = self._load_json(path)
        if existing is None:
            existing = {"entries": []}
        existing["entries"].append(entry)
        self._save_json(path, existing)


# ── Singleton ────────────────────────────────────────────────

_universal_instance: Optional[UniversalDataStore] = None


def get_universal_store() -> UniversalDataStore:
    global _universal_instance
    if _universal_instance is None:
        _universal_instance = UniversalDataStore()
    return _universal_instance
