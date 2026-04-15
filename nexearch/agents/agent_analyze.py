"""
Nexearch — Agent 2: Content Analysis Agent
Sends ALL posts in a SINGLE structured LLM call (Clip 1, Clip 2 … Clip N).
STT is run on the top-5 and bottom-5 outliers BEFORE the main call so
their transcripts are already embedded in the prompt.
"""

import json
import asyncio
from typing import List, Dict, Any
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.llm_router import get_nexearch_llm


BATCH_ANALYSIS_SYSTEM_PROMPT = """\
You are Nexearch Content Analyst — an expert in social media content strategy.
You will receive a numbered list of posts (Clip 1, Clip 2 … Clip N) scraped from a
{platform} account.  Some clips include a spoken transcript from audio analysis.

For EVERY clip return one JSON object inside a top-level "clips" array.
Each object MUST match this exact schema:

{{
  "clip_number": 1,
  "post_id": "<post_id>",
  "hook": {{
    "first_line": "",
    "hook_type": "question|contrarian|statistic|story_open|bold_claim|how_to|list_tease|fear|desire|humor|shock|relatable_pain|authority|challenge|curiosity_gap|social_proof|before_after",
    "hook_strength_score": 0,
    "hook_analysis": "",
    "rewrite_suggestion": ""
  }},
  "caption_structure": {{
    "total_word_count": 0,
    "line_break_pattern": "dense|punchy_short|mixed|single_block",
    "uses_emojis": false,
    "has_cta": false,
    "cta_type": "",
    "cta_strength": 0,
    "caption_length_category": "micro|short|medium|long|essay"
  }},
  "content_analysis": {{
    "primary_topic": "",
    "content_category": "educational|motivational|entertaining|promotional|behind_scenes|testimonial|trend_based|storytelling|controversial|tutorial|personal|news|opinion|how_to|listicle|challenge|duet",
    "format_effectiveness": 0,
    "pacing_style": "fast_cut|medium|slow_build|static|n/a",
    "visual_energy": "high|medium|low|n/a"
  }},
  "audience_psychology": {{
    "primary_emotional_trigger": "",
    "pain_point_addressed": "",
    "desire_addressed": "",
    "scroll_stop_mechanism": "",
    "shareability_reason": ""
  }},
  "writing_quality": {{
    "title_quality_score": 0,
    "caption_quality_score": 0,
    "writing_style": "professional|casual|storytelling|formal|conversational|humorous",
    "power_words_used": []
  }},
  "engagement_tier": "S|A|B|C",
  "tier_rationale": "1-sentence reason for tier based on the raw metrics"
}}

Tier rules (based solely on the raw numbers provided):
  S Tier — top ~10 % by engagement velocity (likes+comments+shares per 1 k views)
  A Tier — top ~25 %
  B Tier — middle 50 %
  C Tier — bottom 25 %

RETURN ONLY VALID JSON:  {{"clips": [...]}}
No markdown fences, no extra keys, no extra text.\
"""


def _stt_transcribe(video_url: str) -> str:
    """Best-effort STT — returns empty string on any failure."""
    try:
        from nexearch.tools.scrapers.stt_utils import transcribe_scraped_post
        result = transcribe_scraped_post(video_url)
        return result or ""
    except Exception as e:
        logger.warning(f"[Agent 2] STT failed for {video_url}: {e}")
        return ""


class ContentAnalysisAgent:
    """
    Agent 2 — Content Analysis
    Sends ALL posts in ONE structured LLM call.
    STT is first run on the top-5 and bottom-5 performance outliers.
    """

    NAME = "content_analysis_agent"

    # How many tokens of caption / description we embed per post
    CAPTION_LIMIT = 700
    DESC_LIMIT    = 300

    def __init__(self):
        self._llm = get_nexearch_llm()

    # ── public entry-point ────────────────────────────────────────────────────
    async def run(self, state: PipelineState) -> PipelineState:
        posts = state.raw_posts
        logger.info(f"[Agent 2] Content Analysis — {len(posts)} posts to analyse")
        state.update_progress("analyze", 20, f"Preparing {len(posts)} posts for analysis...")

        if not posts:
            state.add_error("No posts to analyze")
            return state

        # ── Step A: identify outliers for STT ───────────────────────────────
        posts_sorted = sorted(
            posts,
            key=lambda p: self._engagement_velocity(p),
            reverse=True,
        )
        top5    = posts_sorted[:5]
        bottom5 = posts_sorted[-5:] if len(posts_sorted) >= 10 else []
        stt_targets = top5 + bottom5

        state.update_progress("analyze", 22,
            f"Running STT on {len(stt_targets)} outlier clips (top-5 + bottom-5)...")

        transcripts: Dict[str, str] = {}
        for i, post in enumerate(stt_targets):
            vid_url = post.get("video_url") or post.get("url", "")
            pid     = post.get("post_id", f"p{i}")
            if vid_url and not post.get("transcript"):
                state.update_progress("analyze", 22 + i,
                    f"STT transcribing outlier {i+1}/{len(stt_targets)}...")
                text = await asyncio.to_thread(_stt_transcribe, vid_url)
                if text:
                    transcripts[pid] = text
                    post["transcript"] = text   # embed in place for the prompt

        logger.info(f"[Agent 2] STT completed: {len(transcripts)}/{len(stt_targets)} transcribed")

        # ── Step B: build ONE unified prompt ────────────────────────────────
        state.update_progress("analyze", 32,
            f"Building batch prompt for all {len(posts)} clips...")
        user_msg = self._build_batch_prompt(posts, state.platform)

        # ── Step C: single LLM call ──────────────────────────────────────────
        state.update_progress("analyze", 35,
            f"Sending all {len(posts)} clips to LLM in one call...")
        try:
            system = BATCH_ANALYSIS_SYSTEM_PROMPT.replace("{platform}", state.platform)
            result = self._llm.generate_json(
                system_prompt=system,
                user_message=user_msg,
                temperature=0.2,
                max_tokens=min(8000, 200 * len(posts)),   # ~200 tok/clip
            )
        except Exception as e:
            state.add_error(f"Batch LLM analysis failed: {e}")
            logger.error(f"[Agent 2] LLM call failed: {e}")
            return state

        # ── Step D: parse response ───────────────────────────────────────────
        analyzed = []
        if isinstance(result, dict) and "clips" in result:
            clips = result["clips"]
        elif isinstance(result, list):
            clips = result
        else:
            state.add_error("LLM did not return expected clips structure")
            logger.error(f"[Agent 2] Unexpected LLM response shape: {type(result)}")
            return state

        for clip in clips:
            if not isinstance(clip, dict):
                continue
            pid = clip.get("post_id", "")
            clip["engagement_rate"] = next(
                (p.get("engagement_rate", 0.0) for p in posts if p.get("post_id") == pid),
                0.0,
            )
            analyzed.append(clip)

        state.analyzed_posts = analyzed
        state.analysis_total = len(analyzed)
        state.update_progress("analyze", 40,
            f"Analyzed {state.analysis_total}/{len(posts)} posts in ONE LLM call")
        logger.info(f"[Agent 2] Batch analysis complete: {state.analysis_total} clips analysed")
        return state

    # ── helpers ────────────────────────────────────────────────────────────────
    @staticmethod
    def _engagement_velocity(post: Dict) -> float:
        views    = post.get("views") or post.get("view_count") or 0
        likes    = post.get("likes") or post.get("like_count") or 0
        comments = post.get("comments") or post.get("comment_count") or 0
        shares   = post.get("shares") or post.get("share_count") or 0
        if views > 0:
            return (likes + comments * 2 + shares * 3) / views * 1000
        return float(likes + comments + shares)

    def _build_batch_prompt(self, posts: List[Dict], platform: str) -> str:
        lines = [
            f"Platform: {platform}",
            f"Total clips: {len(posts)}",
            "",
            "Analyze every clip below and return results in the exact JSON schema.",
            "─" * 60,
        ]

        for i, post in enumerate(posts, start=1):
            pid       = post.get("post_id", f"idx_{i}")
            views     = post.get("views") or post.get("view_count", 0)
            likes     = post.get("likes") or post.get("like_count", 0)
            comments  = post.get("comments") or post.get("comment_count", 0)
            shares    = post.get("shares") or post.get("share_count", 0)
            caption   = str(post.get("caption", ""))[:self.CAPTION_LIMIT]
            desc      = str(post.get("description", ""))[:self.DESC_LIMIT]
            title     = str(post.get("title", ""))[:200]
            transcript = str(post.get("transcript", ""))[:800]
            hashtags  = post.get("hashtags", [])
            if isinstance(hashtags, str):
                hashtags = hashtags[:200]
            else:
                hashtags = ", ".join(hashtags[:20])

            block = [
                f"── Clip {i} ──────────────────────────────────",
                f"post_id: {pid}",
                f"views: {views}  likes: {likes}  comments: {comments}  shares: {shares}",
                f"engagement_rate: {post.get('engagement_rate', 0.0):.4f}",
            ]
            if title:      block.append(f"title: {title}")
            if caption:    block.append(f"caption: {caption}")
            if desc:       block.append(f"description: {desc}")
            if hashtags:   block.append(f"hashtags: {hashtags}")
            if transcript: block.append(f"[TRANSCRIPT from audio analysis]: {transcript}")

            lines.extend(block)
            lines.append("")

        return "\n".join(lines)
