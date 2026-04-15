"""
Nexearch — Agent 4: Self-Evolution Engine (Enhanced)
Dual-mode: Client-specific + Universal evolution, per-platform.

Client-Specific Evolution:
  - Per-client, per-platform DNA adjustments
  - Rubric weights tuned to THIS client's performance
  - Writing patterns evolved from THIS client's S/A-tier data

Universal Evolution:
  - Cross-client pattern aggregation per platform
  - Global rubric weights from ALL clients' data
  - Universal DNA = best patterns across all accounts on a platform
"""

import json
import uuid
from typing import Dict, Any, Optional, List
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.llm_router import get_nexearch_llm
from nexearch.tools.embeddings import get_embedding_router
from nexearch.tools.vector_store import get_vector_store
from nexearch.data.client_store import ClientDataStore
from nexearch.data.universal_store import get_universal_store
from nexearch.data.nexclip_client_store import NexClipClientStore


EVOLUTION_SYSTEM_PROMPT = """You are Nexearch Evolution Engine — responsible for self-improvement.
Mode: {mode} evolution for {platform}.
Given the current Account DNA and new scoring results, determine what changes should be made.

Analyze:
1. Are there new patterns in S/A-tier posts not captured in DNA?
2. Are there winning patterns that have shifted or weakened?
3. Should rubric weights be adjusted based on results?
4. Should any new avoidance patterns be added?
5. What writing patterns are consistently performing better?
6. {mode_specific_instruction}

Constraints:
- Maximum 15% change per dimension per cycle
- Changes must have data support (min 3 posts showing the pattern)
- Preserve proven strategies unless data shows decline

RETURN ONLY VALID JSON:
{{
  "changes_made": [
    {{"dimension": "", "old_weight": 0, "new_weight": 0, "reason": ""}}
  ],
  "pattern_updates": {{
    "added_winning_patterns": [],
    "removed_winning_patterns": [],
    "added_avoid_patterns": [],
    "removed_avoid_patterns": [],
    "writing_pattern_updates": []
  }},
  "rubric_updates": [
    {{"dimension": "", "new_weight": 0, "reason": ""}}
  ],
  "dna_updates": {{
    "updated_fields": {{}},
    "writing_dna_updates": {{}},
    "reason": ""
  }},
  "magnitude": 0.0,
  "change_reason": "",
  "recommendation": ""
}}"""


UNIVERSAL_EVOLUTION_PROMPT = """You are the Universal Evolution Engine for {platform}.
You are analyzing patterns across ALL clients to identify universal winning strategies.

Global Winning Patterns (from all clients):
{global_winning}

Global Avoid Patterns:
{global_avoid}

Current Universal DNA:
{universal_dna}

New contributing client data:
{new_client_data}

Synthesize a universal evolution update. Focus on:
1. Patterns that are CONSISTENTLY winning across multiple clients
2. Platform-specific trends that transcend individual accounts
3. Writing patterns that universally perform better on {platform}
4. Content categories that are trending UP or DOWN on {platform}

RETURN ONLY VALID JSON:
{{
  "universal_dna_update": {{
    "top_universal_patterns": [],
    "universal_avoid_patterns": [],
    "platform_trend_signals": [],
    "writing_benchmarks": {{
      "avg_hook_strength": 0,
      "avg_cta_strength": 0,
      "best_caption_length": "",
      "best_hook_types": [],
      "best_writing_styles": []
    }}
  }},
  "rubric_updates": [
    {{"dimension": "", "new_weight": 0, "reason": ""}}
  ],
  "magnitude": 0.0,
  "contributing_clients": [],
  "change_reason": ""
}}"""


class EvolutionAgent:
    """
    Agent 4 — Self-Evolution (Dual Mode)
    Runs BOTH client-specific AND universal evolution per platform.
    """

    NAME = "evolution_agent"

    def __init__(self):
        self._llm = get_nexearch_llm()
        self._embeddings = get_embedding_router()
        self._vector_store = get_vector_store()
        self._universal_store = get_universal_store()

    async def run(self, state: PipelineState) -> PipelineState:
        """Execute dual-mode evolution cycle."""
        logger.info("[Agent 4] Evolution Engine starting (dual-mode)")
        state.update_progress("evolve", 64, "Running evolution analysis...")
        state.evolution_cycle_id = str(uuid.uuid4())

        if not state.account_dna and not state.platform_dna and not state.scored_posts:
            state.add_error("Cannot evolve without DNA and scored posts")
            return state

        platforms = state.get_effective_platforms()

        for platform in platforms:
            try:
                # ── Phase A: Client-Specific Evolution (per platform) ────
                client_changes = await self._run_client_evolution(state, platform)
                state.platform_evolution[platform] = {
                    "changes": client_changes,
                    "cycle_id": state.evolution_cycle_id,
                    "mode": "client",
                }

                # ── Phase B: Universal Evolution (per platform) ──────────
                if state.enable_universal_evolution:
                    universal_changes = await self._run_universal_evolution(state, platform)
                    state.universal_evolution[platform] = {
                        "changes": universal_changes,
                        "mode": "universal",
                    }

                # ── Phase C: Save to data stores ────────────────────────
                await self._persist_evolution(state, platform, client_changes, universal_changes if state.enable_universal_evolution else None)

            except Exception as e:
                state.add_error(f"Evolution failed for {platform}: {e}")
                logger.error(f"[Agent 4] Evolution error on {platform}: {e}")

        # Also handle the primary platform if not in the list
        if state.platform and state.platform not in platforms:
            try:
                client_changes = await self._run_client_evolution(state, state.platform)
                state.evolution_changes = [client_changes] if client_changes else []
                if state.enable_universal_evolution:
                    await self._run_universal_evolution(state, state.platform)
            except Exception as e:
                state.add_error(f"Evolution failed for {state.platform}: {e}")

        if state.platform_evolution:
            state.evolution_changes = [
                {"platform": platform, **payload}
                for platform, payload in state.platform_evolution.items()
                if payload
            ]

        # Store signals in vector store
        await self._store_signals(state)

        state.update_progress("evolve", 70, f"Evolution complete for {len(platforms)} platform(s)")
        logger.info(f"[Agent 4] Evolution complete — {len(platforms)} platforms processed")
        return state

    async def _run_client_evolution(self, state: PipelineState,
                                     platform: str) -> Dict[str, Any]:
        """Run client-specific evolution for a platform."""
        logger.info(f"[Agent 4] Client evolution for {platform}")

        # Get platform-specific DNA and scored posts
        dna = state.platform_dna.get(platform, state.account_dna)
        scored = state.platform_scored.get(platform, {}).get("posts", state.scored_posts)
        tier_dist = state.platform_tier_distributions.get(
            platform, state.tier_distribution
        )

        if not dna or not scored:
            return {}

        mode_instruction = (
            "Focus on THIS specific client's unique patterns and voice. "
            "Preserve what makes their content distinctive."
        )

        user_msg = (
            f"Client: @{state.account_handle} on {platform}\n"
            f"Current Account DNA:\n{json.dumps(dna, default=str)[:4000]}\n\n"
            f"Current Tier Distribution:\n{json.dumps(tier_dist)}\n\n"
            f"Top Scoring Posts (S+A tier):\n"
            f"{json.dumps([s for s in scored if s.get('tier') in ('S', 'A')][:10], default=str)[:3000]}\n\n"
            f"Bottom Posts (C tier):\n"
            f"{json.dumps([s for s in scored if s.get('tier') == 'C'][:5], default=str)[:1500]}"
        )

        system = EVOLUTION_SYSTEM_PROMPT.format(
            mode="Client-Specific", platform=platform,
            mode_specific_instruction=mode_instruction,
        )

        changes = self._llm.generate_json(
            system_prompt=system, user_message=user_msg,
            temperature=0.2, max_tokens=4000,
        ) or {}

        # Apply DNA updates to platform-specific DNA
        if changes.get("dna_updates", {}).get("updated_fields"):
            self._apply_dna_updates(state, platform, changes)

        return changes

    async def _run_universal_evolution(self, state: PipelineState,
                                        platform: str) -> Dict[str, Any]:
        """Run universal evolution for a platform."""
        logger.info(f"[Agent 4] Universal evolution for {platform}")

        # Get global data
        winning = self._universal_store.get_winning_patterns(platform)
        avoid_path = self._universal_store._base_dir / platform / "global_patterns" / "avoid_patterns.json"
        avoid = self._universal_store._load_json(avoid_path) or {"patterns": []}
        universal_dna = self._universal_store.get_universal_dna(platform) or {}

        # Get this client's data as the new contribution
        client_dna = state.platform_dna.get(platform, state.account_dna)
        client_scored = state.platform_scored.get(platform, {}).get("posts", state.scored_posts)

        new_client_data = {
            "client_id": state.client_id,
            "handle": state.account_handle,
            "dna_summary": client_dna.get("content_dna_summary", ""),
            "tier_distribution": state.platform_tier_distributions.get(
                platform, state.tier_distribution
            ),
            "top_patterns": [],
        }

        # Extract top patterns from client DNA
        if client_dna.get("winning_patterns"):
            wp = client_dna["winning_patterns"]
            new_client_data["top_patterns"] = {
                "hooks": wp.get("top_hook_types", []),
                "categories": wp.get("top_content_categories", []),
                "topics": wp.get("top_primary_topics", []),
                "writing": wp.get("writing_patterns", []),
            }

        system = UNIVERSAL_EVOLUTION_PROMPT.format(
            platform=platform,
            global_winning=json.dumps(winning.get("patterns", [])[:20], default=str)[:2000],
            global_avoid=json.dumps(avoid.get("patterns", [])[:10], default=str)[:1000],
            universal_dna=json.dumps(universal_dna, default=str)[:3000],
            new_client_data=json.dumps(new_client_data, default=str)[:2000],
        )

        changes = self._llm.generate_json(
            system_prompt=system, user_message="Generate the universal evolution update now.",
            temperature=0.25, max_tokens=5000,
        ) or {}

        # Aggregate client data into universal store
        if client_dna:
            scored_data = {
                "tier_distribution": state.platform_tier_distributions.get(
                    platform, state.tier_distribution
                ),
            }
            self._universal_store.aggregate_from_client(
                platform, state.client_id, scored_data, client_dna
            )

        # Save universal DNA update
        if changes.get("universal_dna_update"):
            current_version = 1
            existing = self._universal_store.get_universal_dna(platform)
            if existing:
                current_version = existing.get("version", 0) + 1

            changes["universal_dna_update"]["_contributing_clients"] = [state.client_id]
            self._universal_store.save_universal_dna(
                platform, changes["universal_dna_update"], current_version
            )

        # Save universal evolution cycle
        changes["contributing_clients"] = [state.client_id]
        self._universal_store.save_universal_evolution(
            platform, state.evolution_cycle_id, changes
        )

        # Update benchmarks
        if changes.get("universal_dna_update", {}).get("writing_benchmarks"):
            self._universal_store.update_writing_benchmarks(
                platform, changes["universal_dna_update"]["writing_benchmarks"]
            )

        return changes

    def _apply_dna_updates(self, state: PipelineState, platform: str, changes: Dict):
        """Apply evolution updates to platform-specific DNA."""
        updates = changes.get("dna_updates", {}).get("updated_fields", {})
        dna = state.platform_dna.get(platform, state.account_dna)

        for key, value in updates.items():
            if key in dna:
                dna[key] = value

        writing_updates = changes.get("dna_updates", {}).get("writing_dna_updates", {})
        if writing_updates and "writing_dna" in dna:
            for key, value in writing_updates.items():
                if key in dna["writing_dna"]:
                    dna["writing_dna"][key] = value

        state.platform_dna[platform] = dna

    async def _persist_evolution(self, state: PipelineState, platform: str,
                                  client_changes: Dict,
                                  universal_changes: Optional[Dict]):
        """Persist evolution data to client and universal stores."""
        try:
            client_store = ClientDataStore(state.client_id, state.account_handle)

            # Save client-specific evolution
            if client_changes:
                client_store.save_evolution_cycle(
                    platform, state.evolution_cycle_id, client_changes
                )

            # Save updated DNA
            dna = state.platform_dna.get(platform)
            if dna:
                version = 1
                existing = client_store.get_platform_dna(platform)
                if existing:
                    version = existing.get("version", 0) + 1
                client_store.save_platform_dna(platform, dna, version)

        except Exception as e:
            logger.warning(f"Failed to persist evolution data: {e}")

    async def _store_signals(self, state: PipelineState):
        """Store S-tier posts in vector store for RAG retrieval."""
        for post in state.scored_posts:
            if post.get("tier") in ("S", "A"):
                raw = next(
                    (p for p in state.raw_posts if p.get("post_id") == post.get("post_id")),
                    {},
                )
                text = f"{raw.get('caption', '')} {raw.get('title', '')} {raw.get('description', '')}"
                if not text.strip():
                    continue
                try:
                    embedding = self._embeddings.embed(text[:1000])
                    collection = f"nexearch_signals_{state.client_id}"
                    self._vector_store.upsert(
                        collection=collection,
                        id=post.get("post_id", str(uuid.uuid4())),
                        document=text[:2000],
                        embedding=embedding,
                        metadata={
                            "tier": post.get("tier"),
                            "score": post.get("total_score", 0),
                            "platform": state.platform or raw.get("platform", ""),
                            "client_id": state.client_id,
                        },
                    )
                except Exception as e:
                    logger.debug(f"Vector store insert failed: {e}")
