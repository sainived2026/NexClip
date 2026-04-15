"""
Nexearch — Agent 1: Deep Scrape Agent
Orchestrates the scraping process using the configured method.
"""

import asyncio
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.scrapers.factory import create_scraper, get_best_available_scraper
from nexearch.tools.encryption import get_encryptor


class DeepScrapeAgent:
    """
    Agent 1 — Deep Scrape
    Scrapes 100+ posts from a client's social media account.
    Supports all 3 methods with auto-fallback.
    """

    NAME = "deep_scrape_agent"

    async def run(self, state: PipelineState) -> PipelineState:
        """Execute the deep scraping operation."""
        logger.info(f"[Agent 1] Deep Scrape starting for {state.account_handle} on {state.platform}")
        state.update_progress("scrape", 5, "Preparing scraper...")

        if state.skip_scrape:
            logger.info("[Agent 1] Skipping scrape (skip_scrape=True)")
            state.update_progress("scrape", 15, "Scrape skipped — using existing data")
            return state

        start = asyncio.get_event_loop().time()

        # Decrypt credentials if needed
        creds = self._prepare_credentials(state)

        try:
            # Get the appropriate scraper
            scraper = await get_best_available_scraper(
                platform=state.platform,
                client_id=state.client_id,
                preferred_method=state.scraping_method,
                access_token=creds.get("access_token", ""),
                page_id=creds.get("page_id", ""),
                api_key=creds.get("api_key", ""),
                buffer_api_key=creds.get("buffer_api_key", ""),
                metricool_api_key=creds.get("metricool_api_key", ""),
                metricool_user_id=creds.get("metricool_user_id", ""),
                metricool_blog_id=creds.get("metricool_blog_id", ""),
            )

            state.update_progress("scrape", 10, f"Scraping via {scraper.scrape_method_name}...")

            # Execute scrape
            result = await scraper.scrape(
                account_url=state.account_url,
                max_posts=state.max_posts,
                resume_cursor=state.resume_cursor if not state.force_rescrape else None,
                credentials=creds,
            )

            # Process results
            state.raw_posts = [p.model_dump() for p in result.posts]
            state.scrape_total = result.total_scraped
            state.scrape_errors = result.error_messages
            state.scrape_was_blocked = result.was_blocked
            state.resume_cursor = result.resume_cursor

            if result.was_blocked:
                state.add_error(f"Scraping was blocked: {result.blocked_reason}")

            state.update_progress("scrape", 15, f"Scraped {state.scrape_total} posts")
            logger.info(f"[Agent 1] Scrape complete: {state.scrape_total} posts, "
                       f"{len(state.scrape_errors)} errors")

        except Exception as e:
            state.add_error(f"Deep scrape failed: {e}")
            logger.error(f"[Agent 1] Error: {e}")

        state.scrape_duration_seconds = asyncio.get_event_loop().time() - start
        return state

    def _prepare_credentials(self, state: PipelineState) -> Dict[str, Any]:
        """Decrypt and prepare credentials for the scraper."""
        creds = dict(state.get_creds_for_platform(state.platform))
        encryptor = get_encryptor()

        # Decrypt token fields if they look encrypted
        for key in ["access_token", "refresh_token"]:
            if key in creds and creds[key] and encryptor.is_configured:
                try:
                    creds[key] = encryptor.decrypt(creds[key])
                except Exception:
                    pass  # Already plaintext

        return creds
