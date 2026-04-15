"""
Nexearch — Agent 3: Scoring + Account DNA Agent
Scores ALL posts in ONE LLM call, then builds Account DNA in ONE LLM call.
No per-post LLM loops that burn RPD.
"""

import json
from typing import List, Dict, Any
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.llm_router import get_nexearch_llm


BATCH_SCORING_SYSTEM_PROMPT = """\
You are Nexearch Scoring Engine — an expert content performance scorer.

You will receive a list of already-analyzed clips with their raw engagement metrics.
Score EVERY clip using this 5-dimension rubric (100 pts total):

  ENGAGEMENT     (max 30) — Likes/1k views, Comments/1k views, Shares/1k views  
  HOOK           (max 25) — Hook type, strength, scroll-stop power
  VIRALITY       (max 20) — Shareability, emotional triggers, trend alignment
  CONTENT_QUALITY(max 15) — Uniqueness, production quality, authenticity
  PSYCHOLOGY     (max 10) — Pain/desire targeting, identity language

Tier thresholds (strict):
  S (85-100) — exceptional metric velocity + powerful psychology
  A (70-84)  — above-average metrics + strong hooks
  B (50-69)  — baseline
  C  (0-49)  — poor metric conversion + weak hooks

RETURN ONLY VALID JSON:
{
  "scored_clips": [
    {
      "clip_number": 1,
      "post_id": "",
      "tier": "S|A|B|C",
      "total_score": 0,
      "engagement_score": 0,
      "hook_score": 0,
      "virality_score": 0,
      "content_quality_score": 0,
      "psychology_score": 0,
      "scoring_notes": ""
    }
  ]
}
No markdown fences, no extra keys.\
"""


DNA_SYSTEM_PROMPT = """\
You are Nexearch Account DNA Generator.
Given the full scoring results for a {platform} account, synthesize a complete Account DNA.

Analyze S/A-tier posts to extract winning strategies.
Analyze C-tier posts to identify patterns to avoid.

RETURN ONLY VALID JSON:
{
  "winning_patterns": {
    "top_hook_types": [],
    "top_content_categories": [],
    "top_primary_topics": [],
    "dominant_emotional_triggers": [],
    "preferred_caption_length": "micro|short|medium|long",
    "optimal_posting_hours": [],
    "optimal_posting_days": [],
    "writing_patterns": [],
    "title_patterns": [],
    "description_patterns": []
  },
  "avoid_patterns": {
    "weak_hook_types": [],
    "underperforming_topics": [],
    "c_tier_caption_patterns": [],
    "c_tier_title_patterns": [],
    "summary": ""
  },
  "audience_profile": {
    "inferred_audience_description": "",
    "primary_desire": "",
    "primary_fear_pain": "",
    "identity_language": "",
    "engagement_preference": "comments|shares|saves|likes"
  },
  "writing_dna": {
    "vocabulary_style": "",
    "sentence_structure": "",
    "emoji_usage": "none|light|moderate|heavy",
    "power_words": [],
    "opening_patterns": [],
    "closing_patterns": [],
    "cta_patterns": []
  },
  "content_dna_summary": "",
  "nexclip_style_recommendation": {
    "recommended_clip_length_seconds": 38,
    "recommended_hook_style": "",
    "recommended_pacing": "fast_cut|medium|slow_build",
    "recommended_topics": [],
    "tone_descriptor": ""
  }
}\
"""


def _engagement_velocity(raw: Dict) -> float:
    views    = raw.get("views") or raw.get("view_count") or 0
    likes    = raw.get("likes") or raw.get("like_count") or 0
    comments = raw.get("comments") or raw.get("comment_count") or 0
    shares   = raw.get("shares") or raw.get("share_count") or 0
    if views > 0:
        return (likes + comments * 2 + shares * 3) / views * 1000
    return float(likes + comments + shares)


class ScoringDNAAgent:
    """
    Agent 3 — Scoring + Account DNA
    Scores ALL analyzed posts in ONE LLM call.
    Builds Account DNA in ONE LLM call.
    """

    NAME = "scoring_dna_agent"

    def __init__(self):
        self._llm = get_nexearch_llm()

    async def run(self, state: PipelineState) -> PipelineState:
        logger.info(f"[Agent 3] Scoring + DNA — {len(state.analyzed_posts)} analyzed posts")
        state.update_progress("score", 42, "Building batch scoring payload...")

        if not state.analyzed_posts:
            state.add_error("No analyzed posts to score")
            return state

        raw_map = {p.get("post_id", ""): p for p in state.raw_posts}

        # ── Phase A: build batch payload ─────────────────────────────────────
        clips_payload = []
        for i, post in enumerate(state.analyzed_posts, start=1):
            pid = post.get("post_id", "")
            raw = raw_map.get(pid, {})
            views    = raw.get("views")    or raw.get("view_count",    0)
            likes    = raw.get("likes")    or raw.get("like_count",    0)
            comments = raw.get("comments") or raw.get("comment_count", 0)
            shares   = raw.get("shares")   or raw.get("share_count",   0)
            l_1k = round((likes    / views) * 1000, 2) if views else 0
            c_1k = round((comments / views) * 1000, 2) if views else 0
            s_1k = round((shares   / views) * 1000, 2) if views else 0
            clips_payload.append({
                "clip_number": i,
                "post_id": pid,
                "hook_type":   post.get("hook", {}).get("hook_type", ""),
                "hook_strength": post.get("hook", {}).get("hook_strength_score", 0),
                "content_category": post.get("content_analysis", {}).get("content_category", ""),
                "emotional_trigger": post.get("audience_psychology", {}).get("primary_emotional_trigger", ""),
                "writing_style": post.get("writing_quality", {}).get("writing_style", ""),
                "views": views, "likes": likes, "comments": comments, "shares": shares,
                "likes_per_1k_views": l_1k,
                "comments_per_1k_views": c_1k,
                "shares_per_1k_views": s_1k,
                "engagement_rate": raw.get("engagement_rate", 0.0),
            })

        user_msg = (
            f"Account: @{state.account_handle} on {state.platform}\n"
            f"Total clips to score: {len(clips_payload)}\n\n"
            f"CLIPS:\n{json.dumps(clips_payload, default=str)}"
        )

        # ── Phase B: single scoring LLM call ────────────────────────────────
        state.update_progress("score", 45,
            f"Scoring all {len(clips_payload)} clips in ONE LLM call...")
        scored: List[Dict] = []
        try:
            result = self._llm.generate_json(
                system_prompt=BATCH_SCORING_SYSTEM_PROMPT,
                user_message=user_msg,
                temperature=0.15,
                max_tokens=min(8000, 180 * len(clips_payload)),
            )
            if isinstance(result, dict) and "scored_clips" in result:
                scored = result["scored_clips"]
            elif isinstance(result, list):
                scored = result
        except Exception as e:
            state.add_error(f"Batch scoring LLM call failed: {e}")
            logger.error(f"[Agent 3] Scoring LLM failed: {e}")

        # normalise field names
        clean_scored = []
        for s in scored:
            if not isinstance(s, dict):
                continue
            s.setdefault("post_id", "")
            s.setdefault("tier", "B")
            s.setdefault("total_score", 50)
            clean_scored.append(s)

        state.scored_posts = clean_scored

        # tier distribution
        for s in clean_scored:
            tier = s.get("tier", "C")
            if tier in state.tier_distribution:
                state.tier_distribution[tier] += 1

        logger.info(
            f"[Agent 3] Scoring complete. Distribution: {state.tier_distribution}"
        )

        # ── Phase C: single DNA LLM call ────────────────────────────────────
        state.update_progress("score", 56, "Building Account DNA in ONE LLM call...")
        state.account_dna = self._build_dna(state, clean_scored, raw_map)

        state.update_progress("score", 62,
            f"Scoring + DNA complete: {len(clean_scored)} posts scored")
        return state

    # ─────────────────────────────────────────────────────────────────────────
    def _build_dna(
        self,
        state: PipelineState,
        scored: List[Dict],
        raw_map: Dict[str, Dict],
    ) -> Dict[str, Any]:

        analyzed_map = {p.get("post_id", ""): p for p in state.analyzed_posts}

        s_tier = sorted(
            [s for s in scored if s.get("tier") in ("S",)],
            key=lambda x: x.get("total_score", 0), reverse=True,
        )[:10]
        a_tier = sorted(
            [s for s in scored if s.get("tier") == "A"],
            key=lambda x: x.get("total_score", 0), reverse=True,
        )[:10]
        c_tier = sorted(
            [s for s in scored if s.get("tier") == "C"],
            key=lambda x: x.get("total_score", 0),
        )[:10]

        def summarise(tier_list: List[Dict]) -> List[Dict]:
            out = []
            for s in tier_list:
                pid = s.get("post_id", "")
                a   = analyzed_map.get(pid, {})
                r   = raw_map.get(pid, {})
                out.append({
                    "post_id": pid,
                    "tier": s.get("tier"),
                    "score": s.get("total_score"),
                    "hook_type": a.get("hook", {}).get("hook_type"),
                    "category": a.get("content_analysis", {}).get("content_category"),
                    "topic": a.get("content_analysis", {}).get("primary_topic"),
                    "trigger": a.get("audience_psychology", {}).get("primary_emotional_trigger"),
                    "caption_len": a.get("caption_structure", {}).get("caption_length_category"),
                    "writing_style": a.get("writing_quality", {}).get("writing_style"),
                    "engagement_rate": r.get("engagement_rate", 0),
                    "views": r.get("views") or r.get("view_count", 0),
                    "likes": r.get("likes") or r.get("like_count", 0),
                })
            return out

        user_msg = (
            f"Account: @{state.account_handle} on {state.platform}\n"
            f"Total Posts Scored: {len(scored)}\n"
            f"Tier Distribution: {json.dumps(state.tier_distribution)}\n\n"
            f"S-TIER Posts ({len(s_tier)}):\n{json.dumps(summarise(s_tier), default=str)}\n\n"
            f"A-TIER Posts ({len(a_tier)}):\n{json.dumps(summarise(a_tier), default=str)}\n\n"
            f"C-TIER Posts ({len(c_tier)}):\n{json.dumps(summarise(c_tier), default=str)}"
        )

        system = DNA_SYSTEM_PROMPT.replace("{platform}", state.platform)
        dna = self._llm.generate_json(
            system_prompt=system,
            user_message=user_msg,
            temperature=0.25,
            max_tokens=8000,
        )
        return dna or {}
