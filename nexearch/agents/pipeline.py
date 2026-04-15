"""
Nexearch — Pipeline Orchestrator (Enhanced)
6-stage agent pipeline with data store integration.
Saves all results to per-client and universal data directories.
"""

import uuid
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.agents.agent_scrape import DeepScrapeAgent
from nexearch.agents.agent_analyze import ContentAnalysisAgent
from nexearch.agents.agent_score import ScoringDNAAgent
from nexearch.agents.agent_deep_analyze import DeepAnalysisAgent
from nexearch.agents.agent_evolve import EvolutionAgent
from nexearch.agents.agent_bridge import NexClipBridgeAgent
from nexearch.agents.agent_publish import PublisherAgent

from nexearch.data.client_store import ClientDataStore
from nexearch.data.universal_store import get_universal_store
from nexearch.data.nexclip_client_store import NexClipClientStore

# Enforce minimum/maximum post counts for analysis quality
MIN_POSTS_FOR_ANALYSIS = 50
MAX_POSTS_FOR_ANALYSIS = 150


class NexearchPipeline:
    """
    Full 6-stage pipeline orchestrator with data store integration.
    Scrape → Analyze → Score + DNA → Evolve → Bridge → Publish

    Data Flow:
    - Each stage saves results to per-client data directories
    - Evolution runs in dual-mode (client-specific + universal) per platform
    - NexClip enhancements tracked separately per client
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self._callback = progress_callback
        self._agents = [
            ("scrape", DeepScrapeAgent()),
            ("analyze", ContentAnalysisAgent()),
            ("score", ScoringDNAAgent()),
            ("deep_analyze", DeepAnalysisAgent()),
            ("evolve", EvolutionAgent()),
            ("bridge", NexClipBridgeAgent()),
            ("publish", PublisherAgent()),
        ]

    async def run(
        self,
        client_id: str,
        account_url: str,
        platform: str,
        account_handle: str,
        scraping_method: str = "apify",
        publishing_method: str = "metricool",
        credentials: Optional[Dict[str, Any]] = None,
        platform_credentials: Optional[Dict[str, Dict[str, Any]]] = None,
        target_platforms: Optional[list] = None,
        platform_accounts: Optional[Dict[str, str]] = None,
        max_posts: int = MAX_POSTS_FOR_ANALYSIS,
        skip_scrape: bool = False,
        skip_publish: bool = False,
        dry_run: bool = False,
        force_rescrape: bool = False,
        enable_universal_evolution: bool = True,
        analysis_only: bool = True,   # Default: analyse only, never auto-publish
    ) -> PipelineState:
        """Execute the full pipeline with data store integration."""
        # Clamp post count: minimum 50, maximum 150
        max_posts = max(MIN_POSTS_FOR_ANALYSIS, min(max_posts, MAX_POSTS_FOR_ANALYSIS))

        state = PipelineState(
            client_id=client_id,
            account_url=account_url,
            platform=platform,
            account_handle=account_handle,
            scraping_method=scraping_method,
            publishing_method=publishing_method,
            credentials=credentials or {},
            platform_credentials=platform_credentials or {},
            target_platforms=target_platforms or [],
            platform_accounts=platform_accounts or {},
            max_posts=max_posts,
            skip_scrape=skip_scrape,
            skip_publish=skip_publish,
            dry_run=dry_run,
            force_rescrape=force_rescrape,
            enable_universal_evolution=enable_universal_evolution,
            analysis_only=analysis_only,
            pipeline_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
        )

        # Initialize data stores
        client_store = ClientDataStore(client_id, account_handle)
        nexclip_store = NexClipClientStore(client_id, account_handle)
        state.client_data_dir = str(client_store.base_dir)
        state.nexclip_data_dir = str(nexclip_store.base_dir)

        logger.info(
            f"Pipeline {state.pipeline_id} starting for @{account_handle} on {platform}"
            f" | Client data: {state.client_data_dir}"
            f" | NexClip data: {state.nexclip_data_dir}"
        )

        for stage_name, agent in self._agents:
            if stage_name == "deep_analyze" and not state.scored_posts:
                logger.info("Skipping deep analysis because no scored posts are available")
                continue

            # When running analysis-only, never run Bridge or Publish
            if stage_name in ("bridge", "publish") and state.analysis_only:
                logger.info(f"Skipping {stage_name} stage — analysis_only mode")
                continue

            if stage_name == "bridge" and (state.skip_publish or not state.scored_posts):
                logger.info(
                    "Skipping bridge stage because publish flow is disabled"
                    if state.skip_publish
                    else "Skipping bridge stage because no scored posts are available"
                )
                continue

            if stage_name == "publish" and (state.skip_publish or not state.clip_directive):
                logger.info(
                    "Skipping publish stage because skip_publish=True"
                    if state.skip_publish
                    else "Skipping publish stage because no clip directive was generated"
                )
                continue

            try:
                state = await agent.run(state)
                self._emit_progress(state)

                # Save stage results to data stores
                self._persist_stage(state, stage_name, client_store, nexclip_store)

                # Stop if we have no data after scraping
                if (stage_name == "scrape" and state.scrape_was_blocked
                        and not state.raw_posts):
                    state.add_error("Pipeline stopped: scraping was blocked with no data")
                    break

            except Exception as e:
                state.add_error(f"Stage '{stage_name}' crashed: {e}")
                logger.error(f"Pipeline stage {stage_name} failed: {e}")
                break

        state.completed_at = datetime.now(timezone.utc)
        if state.started_at:
            state.total_duration_seconds = (
                state.completed_at - state.started_at
            ).total_seconds()

        state.current_stage = "complete" if not state.errors else "error"
        state.progress_percent = 100

        logger.info(
            f"Pipeline {state.pipeline_id} "
            f"{'completed' if not state.errors else 'completed with errors'} "
            f"in {state.total_duration_seconds:.1f}s — "
            f"Posts: {state.scrape_total} scraped, {state.analysis_total} analyzed, "
            f"{len(state.scored_posts)} scored"
        )

        return state

    def _persist_stage(self, state: PipelineState, stage: str,
                       client_store: ClientDataStore,
                       nexclip_store: NexClipClientStore):
        """Save stage results to the appropriate data stores."""
        try:
            platform = state.platform

            if stage == "scrape" and state.raw_posts:
                client_store.save_scrape(platform, state.raw_posts, {
                    "scrape_method": state.scraping_method,
                    "duration_seconds": state.scrape_duration_seconds,
                    "resume_cursor": state.resume_cursor,
                    "errors": state.scrape_errors,
                })

                # Also save per-platform results
                for p, data in state.platform_scrape_results.items():
                    if data.get("posts"):
                        client_store.save_scrape(p, data["posts"], {
                            "scrape_method": state.scraping_method,
                            "errors": data.get("errors", []),
                        })

            elif stage == "analyze" and state.analyzed_posts:
                client_store.save_analysis(platform, state.analyzed_posts)

                for p, data in state.platform_analysis_results.items():
                    if data.get("posts"):
                        client_store.save_analysis(p, data["posts"])

            elif stage == "score" and state.scored_posts:
                client_store.save_scores(
                    platform, state.scored_posts, state.tier_distribution
                )

                # Save platform-specific DNA
                if state.account_dna:
                    existing = client_store.get_platform_dna(platform)
                    version = (existing.get("version", 0) + 1) if existing else 1
                    client_store.save_platform_dna(platform, state.account_dna, version)

                for p, dna in state.platform_dna.items():
                    existing = client_store.get_platform_dna(p)
                    version = (existing.get("version", 0) + 1) if existing else 1
                    client_store.save_platform_dna(p, dna, version)

                for p, data in state.platform_scored.items():
                    tier_dist = state.platform_tier_distributions.get(p, {})
                    client_store.save_scores(p, data.get("posts", []), tier_dist)

            elif stage == "deep_analyze" and state.deep_analysis_completed:
                logger.debug(f"Deep STT insight stored in state for {platform}.")
                # If Account DNA was enriched with STT insights, update it
                if state.account_dna:
                    existing = client_store.get_platform_dna(platform)
                    version = (existing.get("version", 0) + 1) if existing else 1
                    client_store.save_platform_dna(platform, state.account_dna, version)

            elif stage == "bridge" and state.clip_directive:
                client_store.save_directive(
                    platform, state.directive_id, state.clip_directive
                )

                # Save to NexClip store
                if state.nexclip_system_prompt:
                    nexclip_store.save_prompt_injection(
                        state.nexclip_system_prompt,
                        source_dna_version=0,
                        platform=platform,
                    )

                nexclip_store.save_directive_sent(
                    state.directive_id, state.clip_directive, platform
                )

                # Save writing directives to both stores
                writing = state.clip_directive.get("writing_directives", {})
                if writing:
                    client_store.save_writing_profile(platform, writing)
                    nexclip_store.save_writing_profile(platform, writing)

                # Save per-platform directives
                for p, d_data in state.platform_directives.items():
                    directive = d_data.get("directive", {})
                    d_id = d_data.get("id", str(uuid.uuid4()))
                    client_store.save_directive(p, d_id, directive)
                    nexclip_store.save_directive_sent(d_id, directive, p)

            elif stage == "publish" and state.published_posts:
                for pub in state.published_posts:
                    pub_id = pub.get("publish_id", str(uuid.uuid4()))
                    pub_platform = pub.get("platform", platform)
                    client_store.save_published(pub_platform, pub_id, pub)

        except Exception as e:
            logger.warning(f"Data persistence failed for stage {stage}: {e}")

    def _emit_progress(self, state: PipelineState):
        """Emit progress updates via callback."""
        if self._callback:
            try:
                self._callback({
                    "pipeline_id": state.pipeline_id,
                    "stage": state.current_stage,
                    "progress": state.progress_percent,
                    "message": state.progress_message,
                })
            except Exception:
                pass


async def run_nexearch_pipeline(**kwargs) -> PipelineState:
    """Convenience function to run the pipeline."""
    pipeline = NexearchPipeline()
    return await pipeline.run(**kwargs)
