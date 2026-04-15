"""
Nexearch — NexClip Client Data Store
Tracks what NexClip enhanced for each client individually.
Separate from the main Nexearch client data.

Directory Structure:
nexearch_data/nexclip_clients/
└── {client_id}/
    ├── manifest.json                    # NexClip enhancement manifest
    ├── enhancements/
    │   ├── system_prompts/
    │   │   ├── prompt_{timestamp}.json  # System prompt injections sent to NexClip
    │   │   └── active_prompt.json       # Currently active injection
    │   ├── clip_directives/
    │   │   ├── directive_{id}.json      # ClipDirectives sent to NexClip
    │   │   └── active_directive.json
    │   └── writing_profiles/
    │       └── {platform}_profile.json  # Writing profiles per platform
    ├── processing/
    │   ├── clips_processed/
    │   │   ├── clip_{id}.json           # Individual clip processing records
    │   │   └── processing_log.json
    │   ├── style_adjustments/
    │   │   ├── adjustment_{id}.json
    │   │   └── adjustment_log.json
    │   └── quality_metrics/
    │       ├── quality_{timestamp}.json
    │       └── quality_trend.json
    ├── feedback_loop/
    │   ├── performance_feedback/
    │   │   ├── feedback_{post_id}.json
    │   │   └── feedback_log.json
    │   └── improvement_tracking/
    │       ├── improvement_{cycle}.json
    │       └── improvement_summary.json
    └── exports/
        ├── nexclip_config_export.json   # Full config export for NexClip
        └── enhancement_report.json      # Summary report
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger

from nexearch.config import get_nexearch_settings


def _utcnow_str():
    return datetime.now(timezone.utc).isoformat()


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class NexClipClientStore:
    """
    Per-client NexClip enhancement data store.
    Tracks everything Nexearch sends to NexClip and the results.
    """

    def __init__(self, client_id: str, account_handle: str = ""):
        settings = get_nexearch_settings()
        self._base_dir = (Path(settings.NEXEARCH_CLIENTS_DIR).resolve() /
                          "nexclip_clients" / client_id)
        self._client_id = client_id
        self._account_handle = account_handle
        self._init_directories()

    def _init_directories(self):
        """Create the NexClip client directory tree."""
        subdirs = [
            "enhancements/system_prompts",
            "enhancements/clip_directives",
            "enhancements/writing_profiles",
            "processing/clips_processed",
            "processing/style_adjustments",
            "processing/quality_metrics",
            "feedback_loop/performance_feedback",
            "feedback_loop/improvement_tracking",
            "exports",
        ]
        for d in subdirs:
            (self._base_dir / d).mkdir(parents=True, exist_ok=True)

        manifest_path = self._base_dir / "manifest.json"
        if not manifest_path.exists():
            self._save_json(manifest_path, {
                "client_id": self._client_id,
                "account_handle": self._account_handle,
                "created_at": _utcnow_str(),
                "last_updated": _utcnow_str(),
                "stats": {
                    "total_prompt_injections": 0,
                    "total_directives_sent": 0,
                    "total_clips_processed": 0,
                    "total_style_adjustments": 0,
                    "total_feedback_cycles": 0,
                    "total_improvements_tracked": 0,
                    "quality_trend": "stable",
                },
            })

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ── System Prompt Injections ──────────────────────────────

    def save_prompt_injection(self, prompt: str, source_dna_version: int = 0,
                               platform: str = "all", metadata: Dict = None) -> str:
        """Save a system prompt injection sent to NexClip."""
        ts = _timestamp()
        path = self._base_dir / "enhancements" / "system_prompts" / f"prompt_{ts}.json"
        data = {
            "injection_id": f"inj_{self._client_id}_{ts}",
            "injected_at": _utcnow_str(),
            "prompt": prompt,
            "source_dna_version": source_dna_version,
            "platform": platform,
            "word_count": len(prompt.split()),
            "metadata": metadata or {},
        }
        self._save_json(path, data)

        # Update active
        active_path = self._base_dir / "enhancements" / "system_prompts" / "active_prompt.json"
        self._save_json(active_path, data)

        self._update_manifest("total_prompt_injections", increment=1)
        return data["injection_id"]

    def get_active_prompt(self) -> Optional[Dict]:
        path = self._base_dir / "enhancements" / "system_prompts" / "active_prompt.json"
        return self._load_json(path)

    # ── Clip Directives ───────────────────────────────────────

    def save_directive_sent(self, directive_id: str, directive: Dict,
                             platform: str) -> str:
        """Record a ClipDirective sent to NexClip."""
        path = (self._base_dir / "enhancements" / "clip_directives" /
                f"directive_{directive_id}.json")
        data = {
            "directive_id": directive_id,
            "sent_at": _utcnow_str(),
            "platform": platform,
            "directive": directive,
            "clip_parameters": directive.get("clip_parameters", {}),
            "hook_directive": directive.get("hook_directive", {}),
            "writing_directives": directive.get("writing_directives", {}),
        }
        self._save_json(path, data)

        # Update active
        active_path = (self._base_dir / "enhancements" / "clip_directives" /
                       "active_directive.json")
        self._save_json(active_path, data)

        self._update_manifest("total_directives_sent", increment=1)
        return directive_id

    # ── Writing Profiles ──────────────────────────────────────

    def save_writing_profile(self, platform: str, profile: Dict):
        """Save platform-specific writing profile for NexClip."""
        path = (self._base_dir / "enhancements" / "writing_profiles" /
                f"{platform}_profile.json")
        self._save_json(path, {
            "platform": platform, "updated_at": _utcnow_str(),
            "profile": profile,
        })

    def get_writing_profile(self, platform: str) -> Optional[Dict]:
        path = (self._base_dir / "enhancements" / "writing_profiles" /
                f"{platform}_profile.json")
        return self._load_json(path)

    # ── Clip Processing Records ───────────────────────────────

    def save_clip_processed(self, clip_id: str, processing_data: Dict) -> str:
        """Record a clip processed by NexClip with Nexearch enhancements."""
        path = (self._base_dir / "processing" / "clips_processed" /
                f"clip_{clip_id}.json")
        data = {
            "clip_id": clip_id, "processed_at": _utcnow_str(),
            "enhancements_applied": processing_data.get("enhancements", []),
            "original_title": processing_data.get("original_title", ""),
            "enhanced_title": processing_data.get("enhanced_title", ""),
            "original_caption": processing_data.get("original_caption", ""),
            "enhanced_caption": processing_data.get("enhanced_caption", ""),
            "original_description": processing_data.get("original_description", ""),
            "enhanced_description": processing_data.get("enhanced_description", ""),
            "style_adjustments": processing_data.get("style_adjustments", {}),
            "nexearch_directive_used": processing_data.get("directive_id", ""),
            "quality_score": processing_data.get("quality_score", 0),
        }
        self._save_json(path, data)

        self._append_log(
            self._base_dir / "processing" / "clips_processed" / "processing_log.json",
            {"clip_id": clip_id, "timestamp": _utcnow_str(),
             "quality_score": data["quality_score"]}
        )

        self._update_manifest("total_clips_processed", increment=1)
        return clip_id

    # ── Style Adjustments ─────────────────────────────────────

    def save_style_adjustment(self, adjustment_id: str, adjustment: Dict) -> str:
        """Record a style adjustment made by Nexearch for NexClip."""
        path = (self._base_dir / "processing" / "style_adjustments" /
                f"adjustment_{adjustment_id}.json")
        self._save_json(path, {
            "adjustment_id": adjustment_id, "adjusted_at": _utcnow_str(),
            "adjustment": adjustment,
        })

        self._append_log(
            self._base_dir / "processing" / "style_adjustments" / "adjustment_log.json",
            {"adjustment_id": adjustment_id, "timestamp": _utcnow_str(),
             "type": adjustment.get("type", "unknown")}
        )

        self._update_manifest("total_style_adjustments", increment=1)
        return adjustment_id

    # ── Quality Metrics ───────────────────────────────────────

    def save_quality_metrics(self, metrics: Dict):
        """Save quality metrics snapshot."""
        ts = _timestamp()
        path = (self._base_dir / "processing" / "quality_metrics" /
                f"quality_{ts}.json")
        self._save_json(path, {"timestamp": _utcnow_str(), "metrics": metrics})

        # Update trend
        trend_path = (self._base_dir / "processing" / "quality_metrics" /
                      "quality_trend.json")
        trend = self._load_json(trend_path) or {"data_points": []}
        trend["data_points"].append({
            "timestamp": _utcnow_str(),
            "avg_quality": metrics.get("average_quality_score", 0),
            "total_processed": metrics.get("total_processed", 0),
        })
        # Keep last 100 data points
        trend["data_points"] = trend["data_points"][-100:]
        self._save_json(trend_path, trend)

    # ── Feedback Loop ─────────────────────────────────────────

    def save_performance_feedback(self, post_id: str, feedback: Dict):
        """Record performance feedback from a published post back to NexClip."""
        path = (self._base_dir / "feedback_loop" / "performance_feedback" /
                f"feedback_{post_id}.json")
        self._save_json(path, {
            "post_id": post_id, "feedback_at": _utcnow_str(),
            "platform": feedback.get("platform", ""),
            "performance_metrics": feedback.get("metrics", {}),
            "was_enhancement_effective": feedback.get("effective", None),
            "improvement_vs_baseline": feedback.get("improvement_pct", 0),
            "recommendations": feedback.get("recommendations", []),
        })

        self._append_log(
            self._base_dir / "feedback_loop" / "performance_feedback" / "feedback_log.json",
            {"post_id": post_id, "timestamp": _utcnow_str(),
             "effective": feedback.get("effective", None)}
        )

        self._update_manifest("total_feedback_cycles", increment=1)

    def save_improvement_tracking(self, cycle: int, improvement_data: Dict):
        """Track improvement cycle data."""
        path = (self._base_dir / "feedback_loop" / "improvement_tracking" /
                f"improvement_{cycle}.json")
        self._save_json(path, {
            "cycle": cycle, "tracked_at": _utcnow_str(),
            "data": improvement_data,
        })

        # Update summary
        summary_path = (self._base_dir / "feedback_loop" / "improvement_tracking" /
                        "improvement_summary.json")
        summary = self._load_json(summary_path) or {"cycles": [], "overall_trend": "stable"}
        summary["cycles"].append({
            "cycle": cycle, "timestamp": _utcnow_str(),
            "improvement_pct": improvement_data.get("improvement_pct", 0),
        })
        # Calculate trend
        if len(summary["cycles"]) >= 3:
            recent = [c["improvement_pct"] for c in summary["cycles"][-3:]]
            if all(r > 0 for r in recent):
                summary["overall_trend"] = "improving"
            elif all(r < 0 for r in recent):
                summary["overall_trend"] = "declining"
            else:
                summary["overall_trend"] = "stable"
        self._save_json(summary_path, summary)

        self._update_manifest("total_improvements_tracked", increment=1)

    # ── Exports ───────────────────────────────────────────────

    def export_nexclip_config(self) -> Dict:
        """Export the full NexClip configuration for this client."""
        active_prompt = self.get_active_prompt()
        config = {
            "client_id": self._client_id,
            "exported_at": _utcnow_str(),
            "active_system_prompt": active_prompt.get("prompt", "") if active_prompt else "",
            "writing_profiles": {},
        }

        from nexearch.data.client_store import PLATFORMS
        for platform in PLATFORMS:
            wp = self.get_writing_profile(platform)
            if wp:
                config["writing_profiles"][platform] = wp.get("profile", {})

        path = self._base_dir / "exports" / "nexclip_config_export.json"
        self._save_json(path, config)
        return config

    def generate_enhancement_report(self) -> Dict:
        """Generate a summary report of all NexClip enhancements."""
        manifest = self._load_json(self._base_dir / "manifest.json") or {}
        stats = manifest.get("stats", {})

        report = {
            "client_id": self._client_id,
            "generated_at": _utcnow_str(),
            "stats": stats,
            "active_prompt": (self.get_active_prompt() or {}).get("prompt", "")[:200],
            "quality_trend": stats.get("quality_trend", "stable"),
        }

        path = self._base_dir / "exports" / "enhancement_report.json"
        self._save_json(path, report)
        return report

    # ── Manifest ──────────────────────────────────────────────

    def get_manifest(self) -> Dict:
        return self._load_json(self._base_dir / "manifest.json") or {}

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

    def _update_manifest(self, stat_key: str, value=None, increment: int = None):
        manifest_path = self._base_dir / "manifest.json"
        manifest = self._load_json(manifest_path) or {"stats": {}}
        manifest["last_updated"] = _utcnow_str()
        if increment is not None:
            manifest["stats"][stat_key] = manifest["stats"].get(stat_key, 0) + increment
        elif value is not None:
            manifest["stats"][stat_key] = value
        self._save_json(manifest_path, manifest)
