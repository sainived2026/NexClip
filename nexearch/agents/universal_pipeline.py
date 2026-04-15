"""
Nexearch — Universal Pipeline Runner
Orchestrates continuous global analysis across ALL clients and ALL platforms.
Runs Scrape → Analyze → Score → Evolve in universal mode with live progress tracking,
versioned DNA snapshots (for revert), and detailed evolution logs.
"""

import uuid
import asyncio
import json
import copy
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
from loguru import logger

from nexearch.data.universal_store import get_universal_store, PLATFORMS
from nexearch.data.system_meta import SystemMeta
from nexearch.config import get_nexearch_settings


# ── Disk-backed task registry ─────────────────────────────────────────
# Persists task state to JSON so in-flight tasks survive server restarts.
_running_tasks: Dict[str, Dict] = {}
_TASKS_FILE: Optional[Path] = None


def _get_tasks_file() -> Path:
    global _TASKS_FILE
    if _TASKS_FILE is None:
        settings = get_nexearch_settings()
        data_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        _TASKS_FILE = data_dir / "_pipeline_tasks.json"
    return _TASKS_FILE


def _persist_tasks():
    """Write current task state to disk."""
    try:
        with open(_get_tasks_file(), "w", encoding="utf-8") as f:
            json.dump(_running_tasks, f, indent=2, default=str, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to persist task state: {e}")


def _load_persisted_tasks():
    """Load task state from disk on startup."""
    global _running_tasks
    tf = _get_tasks_file()
    if tf.exists():
        try:
            with open(tf, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Mark any previously-running tasks as lost
            for tid, task in loaded.items():
                if task.get("status") not in ("complete", "error", "cancelled"):
                    task["status"] = "lost"
                    task["message"] = "Server restarted while this task was running"
            _running_tasks.update(loaded)
            logger.info(f"Loaded {len(loaded)} persisted pipeline tasks")
        except Exception as e:
            logger.warning(f"Failed to load persisted tasks: {e}")


# Load on module import
_load_persisted_tasks()


def get_task_status(task_id: str) -> Optional[Dict]:
    return _running_tasks.get(task_id)


def get_all_tasks() -> Dict[str, Dict]:
    return dict(_running_tasks)


class UniversalPipelineRunner:
    """
    Runs the full Nexearch intelligence cycle across ALL clients × ALL platforms.
    
    Two modes:
    1. Global Analysis — scrapes latest posts, analyzes, scores, evolves universally
    2. Force Evolution — skips scraping, re-runs evolution on existing data
    
    Features:
    - Live progress tracking via in-memory task store (polled by frontend)
    - Before/after DNA snapshots for revert capability
    - Detailed evolution logs per cycle
    """

    def __init__(self, task_id: str, mode: str = "full"):
        self.task_id = task_id
        self.mode = mode  # "full" or "evolve_only"
        self.store = get_universal_store()
        self.meta = SystemMeta()
        self._cancelled = False
        self._progress: Dict[str, Any] = {
            "task_id": task_id,
            "mode": mode,
            "status": "initializing",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "current_platform": None,
            "current_client": None,
            "current_stage": None,
            "progress_percent": 0,
            "message": "Initializing universal pipeline...",
            "platforms_completed": [],
            "clients_processed": 0,
            "total_clients": 0,
            "evolution_changes": [],
            "errors": [],
            "completed_at": None,
        }
        _running_tasks[task_id] = self._progress

    def cancel(self):
        self._cancelled = True
        self._update("cancelled", 0, "Pipeline cancelled by user")

    def _update(self, stage: str, percent: int, message: str,
                platform: str = None, client: str = None):
        self._progress["status"] = stage
        self._progress["progress_percent"] = percent
        self._progress["message"] = message
        if platform:
            self._progress["current_platform"] = platform
        if client:
            self._progress["current_client"] = client
        self._progress["current_stage"] = stage
        _running_tasks[self.task_id] = self._progress
        _persist_tasks()

    async def run(self):
        """Execute the universal pipeline."""
        try:
            self._update("starting", 2, "Loading client registry...")

            # Get all registered clients
            clients = self.meta.get_all_client_summaries()
            if not clients:
                # No clients registered — run analysis using public data only
                self._update("analyzing", 5, "No clients registered. Running platform-wide trend analysis...")
                await self._run_platform_trend_analysis()
                return self._progress

            self._progress["total_clients"] = len(clients)

            total_steps = len(PLATFORMS) * len(clients)
            step = 0

            for pi, platform in enumerate(PLATFORMS):
                if self._cancelled:
                    break

                self._update(
                    "analyzing", int((pi / len(PLATFORMS)) * 90) + 5,
                    f"Analyzing {platform}...",
                    platform=platform
                )

                # Snapshot DNA BEFORE evolution for revert capability
                before_dna = copy.deepcopy(self.store.get_universal_dna(platform) or {})
                before_patterns = copy.deepcopy(self.store.get_winning_patterns(platform))

                platform_changes = []

                for ci, client in enumerate(clients):
                    if self._cancelled:
                        break

                    client_id = client.get("client_id", client.get("id", f"client_{ci}"))
                    client_name = client.get("name", client.get("handle", client_id))
                    step += 1

                    pct = int(5 + (step / max(total_steps, 1)) * 85)
                    self._update(
                        "processing",
                        pct,
                        f"[{platform.upper()}] Processing client '{client_name}' ({ci+1}/{len(clients)})",
                        platform=platform,
                        client=client_name
                    )

                    try:
                        changes = await self._run_client_through_pipeline(
                            client_id, client_name, platform
                        )
                        if changes:
                            platform_changes.append({
                                "client_id": client_id,
                                "client_name": client_name,
                                "changes": changes,
                            })
                    except Exception as e:
                        err = f"Error processing {client_name} on {platform}: {str(e)}"
                        self._progress["errors"].append(err)
                        logger.error(err)

                    self._progress["clients_processed"] = step

                # Snapshot DNA AFTER evolution
                after_dna = self.store.get_universal_dna(platform) or {}
                after_patterns = self.store.get_winning_patterns(platform)

                # Save the evolution log entry with before/after for revert
                if platform_changes:
                    log_entry = self._save_evolution_log(
                        platform, before_dna, after_dna,
                        before_patterns, after_patterns,
                        platform_changes
                    )
                    self._progress["evolution_changes"].append(log_entry)

                self._progress["platforms_completed"].append(platform)

            # Final status
            self._update(
                "complete", 100,
                f"Universal analysis complete. {len(self._progress['evolution_changes'])} platforms evolved."
            )
            self._progress["completed_at"] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            self._update("error", 0, f"Pipeline error: {str(e)}")
            self._progress["errors"].append(str(e))
            logger.error(f"Universal pipeline error: {e}")

        return self._progress

    async def _retry_async(self, func, *args, max_retries=3, backoff_factor=2, **kwargs):
        """Helper to retry async functions with exponential backoff."""
        import asyncio
        last_exception = None
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor ** attempt
                    logger.warning(f"Action failed ({e}). Retrying in {sleep_time}s (Attempt {attempt + 1}/{max_retries})...")
                    await asyncio.sleep(sleep_time)
        logger.error(f"Action failed after {max_retries} attempts. Last error: {last_exception}")
        raise last_exception

    async def _run_client_through_pipeline(
        self, client_id: str, client_name: str, platform: str
    ) -> Optional[Dict]:
        """Run a single client through the analysis + evolution stages."""
        from nexearch.data.client_store import ClientDataStore

        try:
            client_store = ClientDataStore(client_id, client_name)

            # Phase 1: Load existing scrape data (or scrape if mode=full)
            existing_scrapes = client_store.get_latest_scrape(platform)
            posts = []

            if existing_scrapes and existing_scrapes.get("posts"):
                posts = existing_scrapes["posts"]
            elif self.mode == "full":
                # Try to scrape (if scraper is configured)
                try:
                    posts = await self._retry_async(self._scrape_client, client_id, client_name, platform)
                except Exception as e:
                    logger.warning(f"Scrape failed for {client_name}/{platform}: {e}")

            if not posts:
                return None

            # Phase 2: Run analysis + scoring via LLM
            analysis = await self._retry_async(self._analyze_and_score, posts, platform, client_name)
            if not analysis:
                return None

            # Phase 3: Run evolution (both client-specific and universal)
            evolution_result = await self._retry_async(
                self._evolve, client_id, client_name, platform, analysis, posts
            )

            return evolution_result

        except Exception as e:
            logger.error(f"Client pipeline error for {client_name}/{platform}: {e}")
            return None

    async def _scrape_client(self, client_id: str, client_name: str, platform: str) -> List:
        """
        Scrape a client's posts using the fallback chain:
        Priority 1: Apify (if APIFY_API_KEY set)
        Priority 2: Platform API (if client has access_token for this platform)
        Priority 3: Crawlee+Playwright (always available as fallback)
        """
        from nexearch.tools.scrapers.factory import get_best_available_scraper
        from nexearch.data.client_store import ClientDataStore

        client_store = ClientDataStore(client_id, client_name)

        # Read credentials from the new credential storage system
        stored_creds = client_store.get_credentials(platform)
        account_url = stored_creds.get("account_url", "")
        access_token = stored_creds.get("access_token", "")
        page_id = stored_creds.get("page_id", "")
        api_key = stored_creds.get("api_key", "")
        login_username = stored_creds.get("login_username", "")
        login_password = stored_creds.get("login_password", "")

        if not account_url:
            # Fallback: try manifest platform config (legacy)
            manifest = client_store.get_manifest()
            platform_config = manifest.get("platforms", {}).get(platform, {})
            account_url = platform_config.get("account_url", "")

        if not account_url:
            # Last resort: construct from account_handle
            manifest = client_store.get_manifest()
            handle = manifest.get("account_handle", client_name)
            url_templates = {
                "instagram": f"https://www.instagram.com/{handle}/",
                "tiktok": f"https://www.tiktok.com/@{handle}",
                "youtube": f"https://www.youtube.com/@{handle}",
                "twitter": f"https://x.com/{handle}",
                "linkedin": f"https://www.linkedin.com/in/{handle}/",
                "facebook": f"https://www.facebook.com/{handle}",
            }
            account_url = url_templates.get(platform, "")

        if not account_url:
            logger.warning(f"No account URL for {client_name}/{platform}, skipping scrape")
            return []

        self._update(
            "scraping", self._progress["progress_percent"],
            f"[{platform.upper()}] Scraping {client_name} via fallback chain...",
            platform=platform, client=client_name
        )

        try:
            scraper = await get_best_available_scraper(
                platform=platform,
                client_id=client_id,
                preferred_method="apify",
                access_token=access_token,
                page_id=page_id,
                api_key=api_key,
            )

            logger.info(f"Using {scraper.scrape_method_name} for {client_name}/{platform}")

            credentials = {}
            if access_token:
                credentials["access_token"] = access_token
            if page_id:
                credentials["page_id"] = page_id
            if api_key:
                credentials["api_key"] = api_key

            result = await scraper.scrape(
                account_url=account_url,
                max_posts=50,
                credentials=credentials if credentials else None,
            )

            if result.had_errors:
                for err in result.error_messages:
                    logger.warning(f"Scrape warning for {client_name}/{platform}: {err}")

            if result.posts:
                # Convert posts to dicts and save to client store
                posts_dicts = []
                for p in result.posts:
                    try:
                        posts_dicts.append(p.model_dump(mode="json") if hasattr(p, "model_dump") else p.__dict__)
                    except Exception:
                        posts_dicts.append({"post_id": str(p.post_id), "caption": str(getattr(p, "caption", ""))})

                client_store.save_scrape(platform, posts_dicts, {
                    "scrape_method": result.scrape_method,
                    "duration_seconds": result.duration_seconds,
                    "errors": result.error_messages,
                })

                logger.info(f"Scraped {len(posts_dicts)} posts for {client_name}/{platform} via {result.scrape_method}")
                return posts_dicts
            else:
                logger.info(f"No posts scraped for {client_name}/{platform}")
                return []

        except Exception as e:
            logger.error(f"Scrape error for {client_name}/{platform}: {e}")
            self._progress["errors"].append(f"Scrape failed for {client_name}/{platform}: {str(e)}")
            return []

    async def _analyze_and_score(
        self, posts: List, platform: str, client_name: str
    ) -> Optional[Dict]:
        """Analyze and score posts using LLM, with Selective STT for outliers."""
        from nexearch.tools.llm_router import get_nexearch_llm
        from nexearch.tools.scrapers.stt_utils import transcribe_scraped_post
        import asyncio

        llm = get_nexearch_llm()

        # Phase 1: Selective STT (Top 5 & Bottom 5)
        # Sort posts by views or likes
        sorted_posts = sorted(
            posts,
            key=lambda x: x.get("views", x.get("view_count", x.get("likes", 0))),
            reverse=True
        )
        
        outliers = sorted_posts[:5] + sorted_posts[-5:] if len(sorted_posts) >= 10 else sorted_posts
        
        for post in outliers:
            vid_url = post.get("video_url") or post.get("url")
            if vid_url and not post.get("transcript"):
                self._update("analyzing", self._progress["progress_percent"], f"[{platform.upper()}] Running Deep STT Analysis on outlier post...")
                try:
                    transcript = await asyncio.to_thread(transcribe_scraped_post, vid_url)
                    if transcript:
                        post["transcript"] = transcript
                except Exception as e:
                    logger.warning(f"Selective STT failed for {vid_url}: {e}")

        # Prepare post summaries for LLM
        post_summaries = []
        for p in posts[:50]:  # Limit to 50 for context window
            post_summaries.append({
                "caption": str(p.get("caption", ""))[:200],
                "transcript": str(p.get("transcript", ""))[:500],
                "likes": p.get("likes", p.get("like_count", 0)),
                "comments": p.get("comments", p.get("comment_count", 0)),
                "views": p.get("views", p.get("view_count", 0)),
                "shares": p.get("shares", p.get("share_count", 0)),
                "type": p.get("type", p.get("media_type", "unknown")),
            })

        if not post_summaries:
            return None

        system_prompt = f"""You are Nexearch Content Analyzer for {platform}.
Analyze these posts and return a JSON with:
{{
    "tier_distribution": {{"S": 0, "A": 0, "B": 0, "C": 0}},
    "winning_patterns": [
        {{"name": "pattern_name", "type": "hook|visual|caption|format", "frequency": 0.0, "description": ""}}
    ],
    "avoid_patterns": [
        {{"name": "pattern_name", "type": "hook|visual|caption|format", "description": ""}}
    ],
    "content_dna": {{
        "tone": "",
        "visual_style": "",
        "caption_style": "",
        "posting_frequency": "",
        "best_content_types": [],
        "engagement_drivers": []
    }},
    "summary": ""
}}
Score each post into tiers: S (top 10%), A (top 25%), B (50%), C (bottom 25%) based on engagement.
RETURN ONLY VALID JSON."""

        try:
            result = llm.generate_json(
                system_prompt=system_prompt,
                user_message=f"Client: {client_name}\nPlatform: {platform}\nPosts ({len(post_summaries)}):\n{json.dumps(post_summaries, default=str)[:6000]}",
                temperature=0.2,
                max_tokens=4000,
            )
            return result
        except Exception as e:
            logger.warning(f"Analysis LLM call failed: {e}")
            return None

    async def _evolve(
        self, client_id: str, client_name: str, platform: str,
        analysis: Dict, posts: List
    ) -> Dict:
        """Run evolution on the analysis results."""
        from nexearch.tools.llm_router import get_nexearch_llm

        llm = get_nexearch_llm()

        # Get current universal state
        current_dna = self.store.get_universal_dna(platform) or {}
        current_winning = self.store.get_winning_patterns(platform)

        system_prompt = f"""You are the Nexearch Universal Evolution Engine for {platform}.
Given the analysis of client "{client_name}" and the current universal intelligence state,
determine what improvements should be made to the universal DNA.

Current Universal DNA:
{json.dumps(current_dna, default=str)[:2000]}

Current Winning Patterns:
{json.dumps(current_winning.get("patterns", [])[:15], default=str)[:1500]}

New Analysis from "{client_name}":
{json.dumps(analysis, default=str)[:3000]}

Generate evolution updates. Focus on:
1. NEW patterns found in this client's data that should be added universally
2. Existing patterns that this client's data reinforces or contradicts
3. DNA fields that should be updated based on new evidence

Constraints: Max 15% change per dimension. Must have data support.

RETURN ONLY VALID JSON:
{{
    "changes_made": [
        {{"dimension": "", "action": "add|modify|remove", "detail": "", "reason": ""}}
    ],
    "new_winning_patterns": [
        {{"name": "", "type": "", "description": "", "confidence": 0.0}}
    ],
    "new_avoid_patterns": [
        {{"name": "", "type": "", "description": ""}}
    ],
    "dna_updates": {{
        "tone": "",
        "visual_style": "",
        "caption_style": "",
        "engagement_drivers": []
    }},
    "magnitude": 0.0,
    "summary": ""
}}"""

        try:
            evolution = llm.generate_json(
                system_prompt=system_prompt,
                user_message="Generate the universal evolution update now.",
                temperature=0.25,
                max_tokens=4000,
            )

            if not evolution:
                return {}

            # Apply winning patterns
            new_wp = evolution.get("new_winning_patterns", [])
            if new_wp:
                self.store.update_winning_patterns(platform, new_wp, client_id)

            # Apply avoid patterns
            new_ap = evolution.get("new_avoid_patterns", [])
            if new_ap:
                self.store.update_avoid_patterns(platform, new_ap, client_id)

            # Apply DNA updates
            dna_updates = evolution.get("dna_updates", {})
            if dna_updates:
                current_version = 1
                existing = self.store.get_universal_dna(platform)
                if existing:
                    current_version = existing.get("version", 0) + 1
                dna_updates["_contributing_clients"] = [client_id]
                self.store.save_universal_dna(platform, dna_updates, current_version)

            # Save evolution cycle
            cycle_id = str(uuid.uuid4())[:8]
            self.store.save_universal_evolution(platform, cycle_id, evolution)

            # Aggregate client data
            self.store.aggregate_from_client(
                platform, client_id,
                {"tier_distribution": analysis.get("tier_distribution", {})},
                analysis.get("content_dna", {})
            )

            return evolution

        except Exception as e:
            logger.error(f"Evolution LLM call failed: {e}")
            return {}

    async def _run_platform_trend_analysis(self):
        """
        Run trend analysis without client data (platform-wide).
        Step 1: Try to discover trending content via Crawlee+Playwright scraping
        Step 2: Feed scraped data + LLM knowledge to generate universal DNA
        
        Scraping fallback chain:
        Priority 1: Apify (if NEXEARCH_APIFY_TOKEN set)
        Priority 2: Crawlee+Playwright (scrape explore/trending pages)
        Priority 3: LLM-only analysis (use model knowledge)
        """
        from nexearch.tools.llm_router import get_nexearch_llm

        llm = get_nexearch_llm()

        # Discovery URLs for trending/explore pages per platform
        discovery_urls = {
            "instagram": "https://www.instagram.com/explore/",
            "tiktok": "https://www.tiktok.com/explore",
            "youtube": "https://www.youtube.com/feed/trending?bp=4gIcGhpnYW1pbmdfY29ycHVzX21vc3RfcG9wdWxhcg%3D%3D",
            "twitter": "https://x.com/explore/tabs/trending",
            "linkedin": "https://www.linkedin.com/feed/",
            "facebook": "https://www.facebook.com/watch/",
        }

        for pi, platform in enumerate(PLATFORMS):
            if self._cancelled:
                break

            pct = int(5 + (pi / len(PLATFORMS)) * 90)
            self._update(
                "discovery_scraping", pct,
                f"Discovering trending content on {platform}...",
                platform=platform
            )

            scraped_posts = []

            # ── Step 1: Try to scrape trending content via fallback chain ──
            try:
                from nexearch.tools.scrapers.factory import get_best_available_scraper

                scraper = await get_best_available_scraper(
                    platform=platform,
                    client_id="nexearch_universal",
                    preferred_method="apify",
                )

                discovery_url = discovery_urls.get(platform, "")
                if discovery_url:
                    self._update(
                        "discovery_scraping", pct,
                        f"[{platform.upper()}] Scraping trending content via {scraper.scrape_method_name}...",
                        platform=platform
                    )

                    result = await scraper.scrape(
                        account_url=discovery_url,
                        max_posts=30,
                    )

                    if result.posts:
                        for p in result.posts:
                            try:
                                scraped_posts.append(
                                    p.model_dump(mode="json") if hasattr(p, "model_dump") else p.__dict__
                                )
                            except Exception:
                                scraped_posts.append({
                                    "post_id": str(getattr(p, "post_id", "")),
                                    "caption": str(getattr(p, "caption", "")),
                                })

                        logger.info(f"Discovered {len(scraped_posts)} trending posts on {platform} via {result.scrape_method}")

                    if result.had_errors:
                        for err in result.error_messages:
                            logger.warning(f"Discovery scraping for {platform}: {err}")

            except Exception as e:
                logger.warning(f"Discovery scraping unavailable for {platform}: {e}")
                self._progress["errors"].append(f"Discovery scrape for {platform}: {str(e)}")

            # ── Step 2: LLM analysis (with or without scraped data) ──
            self._update(
                "trend_analysis", pct + 5,
                f"[{platform.upper()}] Analyzing {'scraped' if scraped_posts else 'platform'} trends via LLM...",
                platform=platform
            )

            try:
                current_dna = self.store.get_universal_dna(platform) or {}

                # Build context from scraped data if available
                scraped_context = ""
                if scraped_posts:
                    post_summaries = []
                    for p in scraped_posts[:30]:
                        post_summaries.append({
                            "caption": str(p.get("caption", ""))[:200],
                            "likes": p.get("likes", p.get("metrics", {}).get("likes", 0)) if isinstance(p.get("metrics"), dict) else p.get("likes", 0),
                            "comments": p.get("comments", p.get("metrics", {}).get("comments", 0)) if isinstance(p.get("metrics"), dict) else p.get("comments", 0),
                            "views": p.get("views", p.get("metrics", {}).get("views", 0)) if isinstance(p.get("metrics"), dict) else p.get("views", 0),
                            "type": p.get("format", p.get("type", "unknown")),
                        })
                    scraped_context = f"""\n\n--- LIVE SCRAPED TRENDING DATA ({len(post_summaries)} posts) ---
The following posts were scraped from {platform}'s trending/explore page RIGHT NOW.
Analyze these real posts to identify what makes them successful:
{json.dumps(post_summaries, default=str)[:4000]}"""

                result = llm.generate_json(
                    system_prompt=f"""You are the Nexearch Trend Analyzer for {platform}.
Based on your knowledge of current {platform} best practices and trends (as of 2026),
generate a universal content DNA profile.{'  You also have LIVE SCRAPED DATA from the platform explore/trending page.' if scraped_posts else ''}

Current DNA (if any): {json.dumps(current_dna, default=str)[:1500]}

RETURN ONLY VALID JSON:
{{
    "winning_patterns": [
        {{"name": "", "type": "hook|visual|caption|format", "description": "", "confidence": 0.8}}
    ],
    "avoid_patterns": [
        {{"name": "", "type": "", "description": ""}}
    ],
    "content_dna": {{
        "tone": "",
        "visual_style": "",
        "caption_style": "",
        "best_content_types": [],
        "engagement_drivers": [],
        "optimal_posting_times": "",
        "hashtag_strategy": ""
    }},
    "platform_trends_2026": [],
    "data_source": "{'live_scrape + llm_knowledge' if scraped_posts else 'llm_knowledge_only'}",
    "posts_analyzed": {len(scraped_posts)},
    "summary": ""
}}""",
                    user_message=f"Generate the latest universal intelligence profile for {platform} in 2026.{scraped_context}",
                    temperature=0.3,
                    max_tokens=4000,
                )

                if result:
                    # Save patterns
                    wp = result.get("winning_patterns", [])
                    if wp:
                        self.store.update_winning_patterns(platform, wp, "nexearch_trends")

                    ap = result.get("avoid_patterns", [])
                    if ap:
                        self.store.update_avoid_patterns(platform, ap, "nexearch_trends")

                    # Save DNA
                    dna = result.get("content_dna", {})
                    if dna:
                        existing = self.store.get_universal_dna(platform)
                        version = (existing.get("version", 0) + 1) if existing else 1
                        dna["_contributing_clients"] = ["nexearch_trends"]
                        dna["_data_source"] = result.get("data_source", "llm_knowledge_only")
                        dna["_posts_analyzed"] = result.get("posts_analyzed", 0)
                        self.store.save_universal_dna(platform, dna, version)

                    # Save trends
                    trends = result.get("platform_trends_2026", [])
                    if trends:
                        self.store.update_trend_signals(platform, {"trends_2026": trends})

                    # Save evolution log entry
                    before_dna = current_dna
                    after_dna = self.store.get_universal_dna(platform) or {}
                    source_label = f"Discovery Scrape ({len(scraped_posts)} posts) + LLM Analysis" if scraped_posts else "LLM Knowledge-Based Analysis"
                    log_entry = self._save_evolution_log(
                        platform, before_dna, after_dna,
                        {"patterns": []}, self.store.get_winning_patterns(platform),
                        [{"client_id": "nexearch_trends", "client_name": source_label,
                          "changes": result}]
                    )
                    self._progress["evolution_changes"].append(log_entry)

            except Exception as e:
                self._progress["errors"].append(f"Trend analysis for {platform}: {str(e)}")
                logger.error(f"Trend analysis error for {platform}: {e}")

            self._progress["platforms_completed"].append(platform)

        self._update("complete", 100, "Platform trend analysis complete.")
        self._progress["completed_at"] = datetime.now(timezone.utc).isoformat()

    def _save_evolution_log(
        self, platform: str,
        before_dna: Dict, after_dna: Dict,
        before_patterns: Dict, after_patterns: Dict,
        client_changes: List[Dict]
    ) -> Dict:
        """Save a detailed evolution log entry with before/after for revert."""
        log_id = str(uuid.uuid4())[:12]
        timestamp = datetime.now(timezone.utc).isoformat()

        log_entry = {
            "log_id": log_id,
            "task_id": self.task_id,
            "platform": platform,
            "timestamp": timestamp,
            "before_dna": before_dna,
            "after_dna": after_dna,
            "before_patterns": before_patterns,
            "after_patterns": after_patterns,
            "client_changes": client_changes,
            "changes_summary": self._summarize_changes(before_dna, after_dna, client_changes),
        }

        # Save to disk
        logs_dir = self.store.base_dir / platform / "global_evolution" / "detailed_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"log_{log_id}.json"

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_entry, f, indent=2, ensure_ascii=False, default=str)

        # Append to master log index
        index_path = self.store.base_dir / platform / "global_evolution" / "log_index.json"
        index = []
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)

        index.append({
            "log_id": log_id,
            "timestamp": timestamp,
            "platform": platform,
            "changes_count": len(client_changes),
            "reverted": False,
        })

        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False, default=str)

        return log_entry

    def _summarize_changes(self, before: Dict, after: Dict, client_changes: List) -> List[str]:
        """Generate human-readable change summaries."""
        summaries = []
        for cc in client_changes:
            changes = cc.get("changes", {})
            if isinstance(changes, dict):
                for change in changes.get("changes_made", []):
                    dim = change.get("dimension", "unknown")
                    action = change.get("action", "updated")
                    detail = change.get("detail", change.get("reason", ""))
                    summaries.append(f"{action.upper()}: {dim} — {detail}")

                for wp in changes.get("new_winning_patterns", []):
                    summaries.append(f"NEW PATTERN: {wp.get('name', 'unknown')} ({wp.get('type', '')})")

                for ap in changes.get("new_avoid_patterns", []):
                    summaries.append(f"AVOID: {ap.get('name', 'unknown')}")

                summary = changes.get("summary", "")
                if summary:
                    summaries.append(f"SUMMARY: {summary}")

        return summaries


def revert_evolution(platform: str, log_id: str) -> Dict:
    """Revert a platform's DNA to the before-state of a specific evolution log."""
    store = get_universal_store()
    logs_dir = store.base_dir / platform / "global_evolution" / "detailed_logs"
    log_path = logs_dir / f"log_{log_id}.json"

    if not log_path.exists():
        return {"success": False, "error": f"Log {log_id} not found for {platform}"}

    with open(log_path, "r", encoding="utf-8") as f:
        log_entry = json.load(f)

    before_dna = log_entry.get("before_dna", {})
    before_patterns = log_entry.get("before_patterns", {})

    # Revert DNA
    if before_dna:
        existing = store.get_universal_dna(platform)
        revert_version = (existing.get("version", 0) + 1) if existing else 1
        before_dna["_contributing_clients"] = [f"revert_from_{log_id}"]
        store.save_universal_dna(platform, before_dna, revert_version)

    # Revert winning patterns
    if before_patterns:
        wp_path = store.base_dir / platform / "global_patterns" / "winning_patterns.json"
        with open(wp_path, "w", encoding="utf-8") as f:
            json.dump(before_patterns, f, indent=2, ensure_ascii=False, default=str)

    # Mark log as reverted
    index_path = store.base_dir / platform / "global_evolution" / "log_index.json"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        for entry in index:
            if entry["log_id"] == log_id:
                entry["reverted"] = True
                entry["reverted_at"] = datetime.now(timezone.utc).isoformat()
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False, default=str)

    return {"success": True, "reverted_to": log_id, "platform": platform}


def start_universal_pipeline(mode: str = "full") -> str:
    """Start the universal pipeline in a background thread. Returns task_id."""
    task_id = str(uuid.uuid4())[:12]
    runner = UniversalPipelineRunner(task_id, mode)

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(runner.run())
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True, name=f"nexearch-universal-{task_id}")
    thread.start()

    return task_id
