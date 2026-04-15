"""
Nexearch — Client Data Store
Ultra-detailed per-client data directory management.

Directory Structure:
nexearch_data/
├── clients/                          # Per-client individual data
│   └── {client_id}/
│       ├── manifest.json             # Master manifest of all client activity
│       ├── scrapes/                   # What Nexearch scraped
│       │   ├── {platform}/
│       │   │   ├── raw_posts/        # Raw scraped post data
│       │   │   │   ├── scrape_{timestamp}.json
│       │   │   │   └── latest.json   # Symlink/copy of most recent
│       │   │   ├── metrics_history/  # Metrics snapshots over time
│       │   │   │   └── metrics_{timestamp}.json
│       │   │   └── scrape_log.json   # Scraping history log
│       │   └── cross_platform/       # Cross-platform merged data
│       │       └── unified_posts.json
│       ├── analysis/                 # What Nexearch analyzed
│       │   ├── {platform}/
│       │   │   ├── analyzed_posts/
│       │   │   │   └── analysis_{timestamp}.json
│       │   │   ├── content_patterns.json
│       │   │   └── writing_patterns.json
│       │   └── cross_platform/
│       │       └── unified_analysis.json
│       ├── intelligence/             # DNA + scoring intelligence
│       │   ├── {platform}/
│       │   │   ├── account_dna/
│       │   │   │   ├── dna_v{version}.json
│       │   │   │   └── current_dna.json
│       │   │   ├── scored_posts/
│       │   │   │   └── scores_{timestamp}.json
│       │   │   ├── tier_distribution.json
│       │   │   └── evolution/        # Platform-specific evolution
│       │   │       ├── cycle_{id}.json
│       │   │       ├── rubric_weights.json
│       │   │       └── evolution_log.json
│       │   └── cross_platform/
│       │       ├── merged_dna.json
│       │       └── merged_evolution.json
│       ├── directives/               # ClipDirectives generated
│       │   ├── {platform}/
│       │   │   ├── directive_{id}.json
│       │   │   └── active_directive.json
│       │   └── writing_profiles/
│       │       └── {platform}_writing.json
│       ├── published/                # What Nexearch uploaded/published
│       │   ├── {platform}/
│       │   │   ├── published_{id}.json
│       │   │   ├── publish_queue.json
│       │   │   ├── performance/
│       │   │   │   ├── perf_{post_id}_{window}.json
│       │   │   │   └── performance_summary.json
│       │   │   └── publish_log.json
│       │   └── cross_platform/
│       │       └── publish_summary.json
│       └── nexclip_enhancements/     # What NexClip enhanced for this client
│           ├── system_prompt_injections/
│           │   ├── injection_{timestamp}.json
│           │   └── active_injection.json
│           ├── clip_processing/
│           │   ├── clip_{id}_enhancement.json
│           │   └── enhancement_log.json
│           └── style_overrides/
│               ├── {platform}_style.json
│               └── override_log.json
├── universal/                        # Cross-client universal intelligence
│   ├── {platform}/
│   │   ├── global_patterns/
│   │   │   ├── winning_patterns.json
│   │   │   ├── avoid_patterns.json
│   │   │   ├── trend_signals.json
│   │   │   └── writing_benchmarks.json
│   │   ├── global_dna/
│   │   │   ├── universal_dna_v{version}.json
│   │   │   └── current_universal_dna.json
│   │   ├── global_evolution/
│   │   │   ├── cycle_{id}.json
│   │   │   ├── rubric_weights.json
│   │   │   └── evolution_log.json
│   │   └── benchmarks/
│   │       ├── engagement_benchmarks.json
│   │       ├── hook_effectiveness.json
│   │       └── content_category_performance.json
│   └── cross_platform/
│       ├── global_trends.json
│       └── cross_platform_insights.json
└── _meta/
    ├── system_status.json
    └── last_sync.json
"""

import json
import os
import shutil
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


class ClientDataStore:
    """
    Per-client data directory manager.
    Handles all file-based data storage with ultra-detailed structure.
    Each client gets their own isolated data directory across all platforms.
    """

    def __init__(self, client_id: str, account_handle: str = ""):
        settings = get_nexearch_settings()
        self._base_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve() / "clients" / client_id
        self._client_id = client_id
        self._account_handle = account_handle
        self._init_directories()

    def _init_directories(self):
        """Create the full directory tree for this client."""
        dirs = [
            "scrapes", "analysis", "intelligence", "directives",
            "published", "nexclip_enhancements", "credentials",
        ]
        for d in dirs:
            for platform in PLATFORMS:
                (self._base_dir / d / platform).mkdir(parents=True, exist_ok=True)
            (self._base_dir / d / "cross_platform").mkdir(parents=True, exist_ok=True)

        # Sub-directories
        for platform in PLATFORMS:
            (self._base_dir / "scrapes" / platform / "raw_posts").mkdir(exist_ok=True)
            (self._base_dir / "scrapes" / platform / "metrics_history").mkdir(exist_ok=True)
            (self._base_dir / "analysis" / platform / "analyzed_posts").mkdir(exist_ok=True)
            (self._base_dir / "intelligence" / platform / "account_dna").mkdir(exist_ok=True)
            (self._base_dir / "intelligence" / platform / "scored_posts").mkdir(exist_ok=True)
            (self._base_dir / "intelligence" / platform / "evolution").mkdir(exist_ok=True)
            (self._base_dir / "directives" / platform).mkdir(exist_ok=True)
            (self._base_dir / "directives" / "writing_profiles").mkdir(exist_ok=True)
            (self._base_dir / "published" / platform / "performance").mkdir(parents=True, exist_ok=True)

        # NexClip enhancement subdirs
        for subdir in ["system_prompt_injections", "clip_processing", "style_overrides"]:
            (self._base_dir / "nexclip_enhancements" / subdir).mkdir(exist_ok=True)

        # Initialize manifest if not exists
        manifest_path = self._base_dir / "manifest.json"
        if not manifest_path.exists():
            self._save_json(manifest_path, {
                "client_id": self._client_id,
                "account_handle": self._account_handle,
                "created_at": _utcnow_str(),
                "last_updated": _utcnow_str(),
                "platforms": {},
                "stats": {
                    "total_scrapes": 0,
                    "total_posts_scraped": 0,
                    "total_posts_analyzed": 0,
                    "total_posts_scored": 0,
                    "total_posts_published": 0,
                    "total_evolution_cycles": 0,
                    "total_directives_generated": 0,
                    "total_nexclip_enhancements": 0,
                },
            })

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    # ── Scrape Data ───────────────────────────────────────────

    def save_scrape(self, platform: str, posts: List[Dict], metadata: Dict = None) -> str:
        """Save scraped raw posts for a platform."""
        ts = _timestamp()
        filename = f"scrape_{ts}.json"
        path = self._base_dir / "scrapes" / platform / "raw_posts" / filename

        data = {
            "scrape_id": f"{self._client_id}_{platform}_{ts}",
            "client_id": self._client_id,
            "platform": platform,
            "scraped_at": _utcnow_str(),
            "total_posts": len(posts),
            "scrape_method": (metadata or {}).get("scrape_method", "unknown"),
            "duration_seconds": (metadata or {}).get("duration_seconds", 0),
            "resume_cursor": (metadata or {}).get("resume_cursor", ""),
            "errors": (metadata or {}).get("errors", []),
            "posts": posts,
        }
        self._save_json(path, data)

        # Update latest.json
        latest_path = self._base_dir / "scrapes" / platform / "raw_posts" / "latest.json"
        self._save_json(latest_path, data)

        # Update scrape log
        self._append_log(
            self._base_dir / "scrapes" / platform / "scrape_log.json",
            {"scrape_id": data["scrape_id"], "timestamp": data["scraped_at"],
             "total_posts": len(posts), "method": data["scrape_method"],
             "file": filename}
        )

        # Update manifest
        self._update_manifest("total_scrapes", increment=1)
        self._update_manifest("total_posts_scraped", increment=len(posts))
        self._update_platform_manifest(platform, "last_scrape", _utcnow_str())
        self._update_platform_manifest(platform, "total_posts_scraped",
                                        increment=len(posts))

        logger.info(f"[ClientDataStore] Saved {len(posts)} posts for {platform} → {filename}")
        return str(path)

    def get_latest_scrape(self, platform: str) -> Optional[Dict]:
        """Get the most recent scrape data for a platform."""
        path = self._base_dir / "scrapes" / platform / "raw_posts" / "latest.json"
        return self._load_json(path)

    def save_metrics_snapshot(self, platform: str, metrics: Dict):
        """Save a metrics snapshot for tracking over time."""
        ts = _timestamp()
        path = self._base_dir / "scrapes" / platform / "metrics_history" / f"metrics_{ts}.json"
        self._save_json(path, {"snapshot_at": _utcnow_str(), "metrics": metrics})

    # ── Analysis Data ─────────────────────────────────────────

    def save_analysis(self, platform: str, analyzed_posts: List[Dict],
                      patterns: Dict = None) -> str:
        """Save analyzed posts for a platform."""
        ts = _timestamp()
        filename = f"analysis_{ts}.json"
        path = self._base_dir / "analysis" / platform / "analyzed_posts" / filename

        data = {
            "analysis_id": f"{self._client_id}_{platform}_analysis_{ts}",
            "client_id": self._client_id,
            "platform": platform,
            "analyzed_at": _utcnow_str(),
            "total_analyzed": len(analyzed_posts),
            "posts": analyzed_posts,
        }
        self._save_json(path, data)

        # Save patterns
        if patterns:
            self._save_json(
                self._base_dir / "analysis" / platform / "content_patterns.json",
                {"updated_at": _utcnow_str(), "patterns": patterns}
            )

        self._update_manifest("total_posts_analyzed", increment=len(analyzed_posts))
        self._update_platform_manifest(platform, "last_analysis", _utcnow_str())

        logger.info(f"[ClientDataStore] Saved {len(analyzed_posts)} analyses for {platform}")
        return str(path)

    def save_writing_patterns(self, platform: str, patterns: Dict):
        """Save writing-specific patterns extracted from analysis."""
        path = self._base_dir / "analysis" / platform / "writing_patterns.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "platform": platform,
                               "patterns": patterns})

    # ── Intelligence Data ─────────────────────────────────────

    def save_scores(self, platform: str, scored_posts: List[Dict],
                    tier_distribution: Dict) -> str:
        """Save scored posts for a platform."""
        ts = _timestamp()
        path = self._base_dir / "intelligence" / platform / "scored_posts" / f"scores_{ts}.json"
        self._save_json(path, {
            "scored_at": _utcnow_str(), "platform": platform,
            "total_scored": len(scored_posts), "tier_distribution": tier_distribution,
            "posts": scored_posts,
        })

        # Update tier distribution
        self._save_json(
            self._base_dir / "intelligence" / platform / "tier_distribution.json",
            {"updated_at": _utcnow_str(), "distribution": tier_distribution}
        )

        self._update_manifest("total_posts_scored", increment=len(scored_posts))
        self._update_platform_manifest(platform, "last_scoring", _utcnow_str())
        self._update_platform_manifest(platform, "tier_distribution", tier_distribution)
        return str(path)

    def save_platform_dna(self, platform: str, dna: Dict, version: int = 1) -> str:
        """Save platform-specific Account DNA with versioning."""
        # Save versioned copy
        versioned_path = (self._base_dir / "intelligence" / platform /
                          "account_dna" / f"dna_v{version}.json")
        dna_data = {
            "version": version, "platform": platform,
            "created_at": _utcnow_str(), "client_id": self._client_id,
            "dna": dna,
        }
        self._save_json(versioned_path, dna_data)

        # Update current
        current_path = (self._base_dir / "intelligence" / platform /
                        "account_dna" / "current_dna.json")
        self._save_json(current_path, dna_data)

        self._update_platform_manifest(platform, "dna_version", version)
        self._update_platform_manifest(platform, "last_dna_update", _utcnow_str())

        logger.info(f"[ClientDataStore] Saved DNA v{version} for {platform}")
        return str(current_path)

    def get_platform_dna(self, platform: str) -> Optional[Dict]:
        """Get current platform-specific DNA."""
        path = (self._base_dir / "intelligence" / platform /
                "account_dna" / "current_dna.json")
        return self._load_json(path)

    def save_evolution_cycle(self, platform: str, cycle_id: str,
                              evolution_data: Dict) -> str:
        """Save a platform-specific evolution cycle."""
        path = (self._base_dir / "intelligence" / platform /
                "evolution" / f"cycle_{cycle_id}.json")
        self._save_json(path, {
            "cycle_id": cycle_id, "platform": platform,
            "evolved_at": _utcnow_str(), "data": evolution_data,
        })

        # Update evolution log
        self._append_log(
            self._base_dir / "intelligence" / platform / "evolution" / "evolution_log.json",
            {"cycle_id": cycle_id, "timestamp": _utcnow_str(),
             "magnitude": evolution_data.get("magnitude", 0)}
        )

        # Update rubric weights
        if evolution_data.get("changes_made"):
            weights_path = (self._base_dir / "intelligence" / platform /
                            "evolution" / "rubric_weights.json")
            existing = self._load_json(weights_path) or {"weights": {}, "history": []}
            for change in evolution_data["changes_made"]:
                dim = change.get("dimension", "")
                existing["weights"][dim] = change.get("new_weight", 0)
            existing["history"].append({"cycle_id": cycle_id, "timestamp": _utcnow_str()})
            self._save_json(weights_path, existing)

        self._update_manifest("total_evolution_cycles", increment=1)
        self._update_platform_manifest(platform, "last_evolution", _utcnow_str())
        self._update_platform_manifest(platform, "evolution_cycles",
                                        increment=1)
        return str(path)

    # ── Directive Data ────────────────────────────────────────

    def save_directive(self, platform: str, directive_id: str,
                       directive: Dict) -> str:
        """Save a ClipDirective for a specific platform."""
        path = self._base_dir / "directives" / platform / f"directive_{directive_id}.json"
        self._save_json(path, {
            "directive_id": directive_id, "platform": platform,
            "created_at": _utcnow_str(), "directive": directive,
        })

        # Update active directive
        active_path = self._base_dir / "directives" / platform / "active_directive.json"
        self._save_json(active_path, {
            "directive_id": directive_id, "platform": platform,
            "activated_at": _utcnow_str(), "directive": directive,
        })

        self._update_manifest("total_directives_generated", increment=1)
        self._update_platform_manifest(platform, "active_directive_id", directive_id)
        return str(path)

    def save_writing_profile(self, platform: str, profile: Dict):
        """Save platform-specific writing profile."""
        path = self._base_dir / "directives" / "writing_profiles" / f"{platform}_writing.json"
        self._save_json(path, {"platform": platform, "updated_at": _utcnow_str(),
                               "profile": profile})

    # ── Published Data ────────────────────────────────────────

    def save_published(self, platform: str, publish_id: str,
                       publish_data: Dict) -> str:
        """Save published post data."""
        path = self._base_dir / "published" / platform / f"published_{publish_id}.json"
        self._save_json(path, {
            "publish_id": publish_id, "platform": platform,
            "published_at": _utcnow_str(), "data": publish_data,
        })

        self._append_log(
            self._base_dir / "published" / platform / "publish_log.json",
            {"publish_id": publish_id, "timestamp": _utcnow_str(),
             "status": publish_data.get("status", "published")}
        )

        self._update_manifest("total_posts_published", increment=1)
        self._update_platform_manifest(platform, "last_publish", _utcnow_str())
        self._update_platform_manifest(platform, "total_published", increment=1)
        return str(path)

    def save_performance(self, platform: str, post_id: str,
                         window: str, perf_data: Dict):
        """Save performance results for a published post at a specific window."""
        path = (self._base_dir / "published" / platform / "performance" /
                f"perf_{post_id}_{window}.json")
        self._save_json(path, {
            "post_id": post_id, "platform": platform, "window": window,
            "polled_at": _utcnow_str(), "metrics": perf_data,
        })

    def save_publish_queue(self, platform: str, queue: List[Dict]):
        """Save the current publish queue."""
        path = self._base_dir / "published" / platform / "publish_queue.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "queue": queue})

    # ── NexClip Enhancement Data ──────────────────────────────

    def save_nexclip_injection(self, prompt: str, metadata: Dict = None) -> str:
        """Save a NexClip system prompt injection."""
        ts = _timestamp()
        path = (self._base_dir / "nexclip_enhancements" /
                "system_prompt_injections" / f"injection_{ts}.json")
        data = {
            "injected_at": _utcnow_str(), "prompt": prompt,
            "metadata": metadata or {},
        }
        self._save_json(path, data)

        # Update active injection
        active_path = (self._base_dir / "nexclip_enhancements" /
                       "system_prompt_injections" / "active_injection.json")
        self._save_json(active_path, data)

        self._update_manifest("total_nexclip_enhancements", increment=1)
        return str(path)

    def save_clip_enhancement(self, clip_id: str, enhancement: Dict) -> str:
        """Save what NexClip enhanced for a specific clip."""
        path = (self._base_dir / "nexclip_enhancements" /
                "clip_processing" / f"clip_{clip_id}_enhancement.json")
        data = {
            "clip_id": clip_id, "enhanced_at": _utcnow_str(),
            "enhancement": enhancement,
        }
        self._save_json(path, data)

        self._append_log(
            self._base_dir / "nexclip_enhancements" / "clip_processing" / "enhancement_log.json",
            {"clip_id": clip_id, "timestamp": _utcnow_str(),
             "type": enhancement.get("type", "unknown")}
        )
        return str(path)

    def save_style_override(self, platform: str, override: Dict):
        """Save NexClip style override for a platform."""
        path = (self._base_dir / "nexclip_enhancements" /
                "style_overrides" / f"{platform}_style.json")
        self._save_json(path, {"platform": platform, "updated_at": _utcnow_str(),
                               "override": override})

        self._append_log(
            self._base_dir / "nexclip_enhancements" / "style_overrides" / "override_log.json",
            {"platform": platform, "timestamp": _utcnow_str()}
        )

    # ── Credential Management ─────────────────────────────────

    def save_credentials(self, platform: str, credentials: Dict) -> str:
        """
        Save platform credentials for this client.
        
        Credentials structure:
        {
            "account_url": "https://instagram.com/username",      # Method 1: Page link
            "login_username": "username",                          # Method 2: Playwright login
            "login_password": "password",                          # Method 2: Playwright login
            "access_token": "token",                               # Method 3: Platform API
            "api_key": "key",                                      # Method 3: Platform API
            "page_id": "123456",                                   # Method 3: Platform API (FB/IG)
            "metricool_api_key": "key",                             # Method 4: Metricool upload method
            "buffer_api_key": "key",                                # Method 5: Buffer API (research + upload)
        }
        """
        creds_dir = self._base_dir / "credentials" / platform
        creds_dir.mkdir(parents=True, exist_ok=True)
        path = creds_dir / "credentials.json"

        # Load existing credentials and merge
        existing = self._load_json(path) or {}
        existing_creds = existing.get("credentials", {})

        incoming_account_url = str(credentials.get("account_url", "") or "").strip()
        existing_account_url = str(existing_creds.get("account_url", "") or "").strip()
        if not existing_account_url and not incoming_account_url:
            raise ValueError(
                f"account_url is mandatory when adding {platform} credentials for client '{self._client_id}'"
            )

        # Only update non-empty values (don't erase existing with blanks)
        for key, value in credentials.items():
            if value is not None and str(value).strip():
                existing_creds[key] = value

        data = {
            "platform": platform,
            "client_id": self._client_id,
            "updated_at": _utcnow_str(),
            "credentials": existing_creds,
        }
        self._save_json(path, data)

        # Update manifest with access capabilities
        has_url = bool(existing_creds.get("account_url", ""))
        has_login = bool(existing_creds.get("login_username")) and bool(existing_creds.get("login_password"))
        has_api = bool(existing_creds.get("access_token") or existing_creds.get("api_key"))
        has_metricool = bool(existing_creds.get("metricool_api_key"))
        has_buffer = bool(existing_creds.get("buffer_api_key"))

        self._update_platform_manifest(platform, "account_url", existing_creds.get("account_url", ""))
        self._update_platform_manifest(platform, "has_page_link", has_url)
        self._update_platform_manifest(platform, "has_login_creds", has_login)
        self._update_platform_manifest(platform, "has_api_key", has_api)
        self._update_platform_manifest(platform, "has_metricool", has_metricool)
        self._update_platform_manifest(platform, "has_buffer", has_buffer)
        self._update_platform_manifest(platform, "can_research", has_url or has_login or has_api or has_metricool or has_buffer)
        self._update_platform_manifest(platform, "can_upload", has_login or has_api or has_metricool or has_buffer)

        logger.info(f"[ClientDataStore] Saved credentials for {platform} (url={has_url}, login={has_login}, api={has_api}, metricool={has_metricool}, buffer={has_buffer})")
        return str(path)

    def get_credentials(self, platform: str) -> Dict:
        """Get stored credentials for a platform. Returns empty dict if none."""
        path = self._base_dir / "credentials" / platform / "credentials.json"
        data = self._load_json(path)
        if data:
            return data.get("credentials", {})
        return {}

    def get_platform_capabilities(self, platform: str) -> Dict:
        """
        Get access capabilities for a platform.
        Returns: {
            "can_research": bool,
            "can_upload": bool,
            "methods": {"page_link": bool, "login_creds": bool, "api_key": bool, "metricool": bool, "buffer": bool},
            "account_url": str,
        }
        """
        manifest = self.get_manifest()
        p_data = manifest.get("platforms", {}).get(platform, {})

        return {
            "platform": platform,
            "can_research": p_data.get("can_research", False),
            "can_upload": p_data.get("can_upload", False),
            "methods": {
                "page_link": p_data.get("has_page_link", False),
                "login_creds": p_data.get("has_login_creds", False),
                "api_key": p_data.get("has_api_key", False),
                "metricool": p_data.get("has_metricool", False),
                "buffer": p_data.get("has_buffer", False),
            },
            "account_url": p_data.get("account_url", ""),
        }

    def get_all_capabilities(self) -> Dict:
        """Get capabilities summary across all platforms."""
        result = {
            "client_id": self._client_id,
            "platforms": {},
            "summary": {
                "total_researchable": 0,
                "total_uploadable": 0,
                "research_only": [],
                "full_access": [],
                "no_access": [],
            }
        }
        for platform in PLATFORMS:
            caps = self.get_platform_capabilities(platform)
            result["platforms"][platform] = caps
            if caps["can_research"] and caps["can_upload"]:
                result["summary"]["total_uploadable"] += 1
                result["summary"]["total_researchable"] += 1
                result["summary"]["full_access"].append(platform)
            elif caps["can_research"]:
                result["summary"]["total_researchable"] += 1
                result["summary"]["research_only"].append(platform)
            else:
                result["summary"]["no_access"].append(platform)
        return result

    def update_platform_config(self, platform: str, account_url: str = "",
                                login_username: str = "", login_password: str = "",
                                access_token: str = "", api_key: str = "",
                                page_id: str = "", metricool_api_key: str = "",
                                buffer_api_key: str = "") -> str:
        """
        Convenience method to set all credential fields at once for a platform.
        Only non-empty values are written (won't erase existing).
        """
        creds = {}
        if account_url: creds["account_url"] = account_url
        if login_username: creds["login_username"] = login_username
        if login_password: creds["login_password"] = login_password
        if access_token: creds["access_token"] = access_token
        if api_key: creds["api_key"] = api_key
        if page_id: creds["page_id"] = page_id
        if metricool_api_key: creds["metricool_api_key"] = metricool_api_key
        if buffer_api_key: creds["buffer_api_key"] = buffer_api_key
        return self.save_credentials(platform, creds)

    # ── Cross-Platform Aggregation ────────────────────────────

    def save_unified_posts(self, posts: List[Dict]):
        """Save cross-platform unified post data."""
        path = self._base_dir / "scrapes" / "cross_platform" / "unified_posts.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "total": len(posts),
                               "posts": posts})

    def save_unified_analysis(self, analysis: Dict):
        """Save cross-platform unified analysis."""
        path = self._base_dir / "analysis" / "cross_platform" / "unified_analysis.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "analysis": analysis})

    def save_merged_dna(self, dna: Dict):
        """Save cross-platform merged DNA."""
        path = self._base_dir / "intelligence" / "cross_platform" / "merged_dna.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "dna": dna})

    def save_publish_summary(self, summary: Dict):
        """Save cross-platform publish summary."""
        path = self._base_dir / "published" / "cross_platform" / "publish_summary.json"
        self._save_json(path, {"updated_at": _utcnow_str(), "summary": summary})

    # ── Manifest ──────────────────────────────────────────────

    def get_manifest(self) -> Dict:
        """Get the client manifest."""
        return self._load_json(self._base_dir / "manifest.json") or {}

    def get_client_summary(self) -> Dict:
        """Get a human-readable summary of all client data."""
        manifest = self.get_manifest()
        summary = {
            "client_id": self._client_id,
            "account_handle": self._account_handle,
            "stats": manifest.get("stats", {}),
            "platforms": {},
        }
        for platform in PLATFORMS:
            p_data = manifest.get("platforms", {}).get(platform, {})
            if p_data:
                summary["platforms"][platform] = {
                    "total_scraped": p_data.get("total_posts_scraped", 0),
                    "total_published": p_data.get("total_published", 0),
                    "dna_version": p_data.get("dna_version", 0),
                    "evolution_cycles": p_data.get("evolution_cycles", 0),
                    "last_activity": p_data.get("last_scrape", "never"),
                }
        return summary

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

    def _update_platform_manifest(self, platform: str, key: str,
                                   value=None, increment: int = None):
        manifest_path = self._base_dir / "manifest.json"
        manifest = self._load_json(manifest_path) or {"platforms": {}}
        if "platforms" not in manifest:
            manifest["platforms"] = {}
        if platform not in manifest["platforms"]:
            manifest["platforms"][platform] = {}
        if increment is not None:
            manifest["platforms"][platform][key] = (
                manifest["platforms"][platform].get(key, 0) + increment
            )
        elif value is not None:
            manifest["platforms"][platform][key] = value
        self._save_json(manifest_path, manifest)
