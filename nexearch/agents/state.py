"""
Nexearch — Pipeline State (Enhanced)
Shared state with dual-mode (client-specific + universal) support.
Platform-specific evolution tracking.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class PipelineState:
    """Shared state flowing through the Nexearch agent pipeline."""

    # ── Context ───────────────────────────────────────────────
    client_id: str = ""
    account_url: str = ""
    platform: str = ""                    # Primary platform for THIS run
    account_handle: str = ""
    scraping_method: str = "apify"
    publishing_method: str = "metricool"

    # ── Multi-Platform Context ────────────────────────────────
    target_platforms: List[str] = field(default_factory=list)
    # When populated, scrape/evolve across ALL these platforms individually
    # Each platform gets its own DNA, evolution, and directives
    platform_accounts: Dict[str, str] = field(default_factory=dict)
    # Maps platform → account_url (for multi-platform clients)

    # ── Stage 1: Scraping Output ──────────────────────────────
    raw_posts: List[Dict[str, Any]] = field(default_factory=list)
    scrape_total: int = 0
    scrape_errors: List[str] = field(default_factory=list)
    scrape_was_blocked: bool = False
    scrape_duration_seconds: float = 0.0
    resume_cursor: str = ""

    # Per-platform scraping results
    platform_scrape_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # { "instagram": { "posts": [...], "total": N, "errors": [...] }, ... }

    # ── Stage 2: Analysis Output ──────────────────────────────
    analyzed_posts: List[Dict[str, Any]] = field(default_factory=list)
    analysis_total: int = 0
    analysis_errors: List[str] = field(default_factory=list)

    # Per-platform analysis
    platform_analysis_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # ── Stage 3: Scoring Output ───────────────────────────────
    scored_posts: List[Dict[str, Any]] = field(default_factory=list)
    tier_distribution: Dict[str, int] = field(default_factory=lambda: {"S": 0, "A": 0, "B": 0, "C": 0})
    account_dna: Dict[str, Any] = field(default_factory=dict)

    # Per-platform DNA (platform-specific evolution)
    platform_dna: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # { "instagram": { ... }, "tiktok": { ... }, ... }
    platform_scored: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    platform_tier_distributions: Dict[str, Dict[str, int]] = field(default_factory=dict)

    platform_tiered_posts: Dict[str, Dict[str, List[Dict[str, Any]]]] = field(default_factory=dict)
    
    # ── Stage 3.5: Deep STT Analysis Output ───────────────────
    deep_analysis_completed: bool = False
    deep_analysis_errors: List[str] = field(default_factory=list)
    deep_analyzed_posts: List[Dict[str, Any]] = field(default_factory=list)
    stt_transcripts: Dict[str, str] = field(default_factory=dict) # post_id -> transcript text

    # ── Stage 4: Evolution Output ─────────────────────────────
    evolution_changes: List[Dict[str, Any]] = field(default_factory=list)
    evolution_cycle_id: str = ""
    evolution_mode: str = "client"         # "client" or "universal" or "both"

    # Per-platform evolution
    platform_evolution: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # { "instagram": { "changes": [...], "cycle_id": "..." }, ... }
    universal_evolution: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # { "instagram": { "global_patterns_updated": N, ... }, ... }

    # ── Stage 5: Bridge Output ────────────────────────────────
    clip_directive: Dict[str, Any] = field(default_factory=dict)
    directive_id: str = ""
    nexclip_system_prompt: str = ""

    # Per-platform directives
    platform_directives: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # { "instagram": { "directive": {}, "id": "..." }, ... }

    # ── Stage 6: Publishing Output ────────────────────────────
    published_posts: List[Dict[str, Any]] = field(default_factory=list)
    publish_errors: List[str] = field(default_factory=list)

    # ── Pipeline Metadata ─────────────────────────────────────
    pipeline_id: str = ""
    current_stage: str = "init"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    progress_percent: int = 0
    progress_message: str = ""

    # ── Credentials (decrypted, in-memory only) ──────────────
    credentials: Dict[str, Any] = field(default_factory=dict)
    # Per-platform credentials
    platform_credentials: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # { "instagram": { "access_token": "..." }, "youtube": { "api_key": "..." } }

    # ── Options ───────────────────────────────────────────────
    max_posts: int = 100
    skip_scrape: bool = False
    skip_publish: bool = False
    force_rescrape: bool = False
    dry_run: bool = False
    analysis_only: bool = False            # When True: stop after Evolve, never run Bridge/Publish
    enable_universal_evolution: bool = True   # Also run universal evolution
    scrape_all_platforms: bool = False         # Scrape all 6 platforms

    # ── Data Store Paths (populated during pipeline run) ──────
    client_data_dir: str = ""
    nexclip_data_dir: str = ""

    def add_error(self, msg: str):
        self.errors.append(msg)

    def update_progress(self, stage: str, percent: int, message: str = ""):
        self.current_stage = stage
        self.progress_percent = percent
        self.progress_message = message

    def get_effective_platforms(self) -> List[str]:
        """Get the list of platforms to process."""
        if self.target_platforms:
            return self.target_platforms
        return [self.platform] if self.platform else []

    def get_creds_for_platform(self, platform: str) -> Dict[str, Any]:
        """Get credentials for a specific platform."""
        return self.platform_credentials.get(platform, self.credentials)
