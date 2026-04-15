"""
Nexearch — Agent 3.5: Deep Structural Analysis Agent
Uses STT transcripts already captured by ContentAnalysisAgent (Agent 2) to
perform a deep LLM comparison of top vs bottom performing clips.
No video downloads. No duplicate STT calls.
"""

import json
from typing import Dict, Any
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.llm_router import get_nexearch_llm


DEEP_ANALYSIS_SYSTEM_PROMPT = """\
You are Nexearch Deep Structural Analyst.
Compare the exact word-for-word transcripts of this client's TOP PERFORMING
clips against their LEAST PERFORMING clips.

Identify WHY the top ones succeeded and the bottom ones failed by analysing:
1. Pacing & Information Velocity — are winning videos faster, denser, or more strategic?
2. Hook Structure — how do the exact first 15 words differ mathematically and psychologically?
3. Vocabulary & Tone — what specific power words or cadences appear in the winners?
4. Delivery Flaws — what did C-tier clips do structurally wrong?

RETURN ONLY VALID JSON:
{
  "deep_insights": [
    "List of 5-7 extremely specific structural insights based purely on transcript data"
  ],
  "structural_winners": {
    "optimal_wpm_pacing": "fast|medium|slow|dynamic",
    "winning_vocabulary": ["list of words/phrases"],
    "hook_formula": "The exact script formula that worked best",
    "retention_mechanisms": ["list of structural ways they kept attention"]
  },
  "structural_losers": {
    "failing_vocabulary": [],
    "pacing_flaws": "What was wrong with the timing in C-tier?",
    "hook_failures": "Why the exact words in the C-tier hooks failed"
  }
}\
"""


class DeepAnalysisAgent:
    """
    Agent 3.5 — Deep Structural Analysis
    Uses STT transcripts already stored in state.stt_transcripts (captured
    during Agent 2 batch analysis) to run a single LLM deep-comparison call.
    """

    NAME = "deep_analysis_agent"

    def __init__(self, top_n: int = 5, bottom_n: int = 5):
        self._llm = get_nexearch_llm()
        self.top_n = top_n
        self.bottom_n = bottom_n

    async def run(self, state: PipelineState) -> PipelineState:
        logger.info("[Agent 3.5] Deep Structural Analysis — using pre-captured STT transcripts")
        state.update_progress("deep_analyze", 62, "Preparing structural comparison from transcripts...")

        if not state.scored_posts:
            state.add_error("No scored posts available for deep analysis.")
            return state

        # Use scores to identify top/bottom
        s_a_tier = sorted(
            [p for p in state.scored_posts if p.get("tier") in ("S", "A")],
            key=lambda x: x.get("total_score", 0), reverse=True,
        )[:self.top_n]

        c_tier = sorted(
            [p for p in state.scored_posts if p.get("tier") == "C"],
            key=lambda x: x.get("total_score", 0),
        )[:self.bottom_n]

        targets_top    = s_a_tier
        targets_bottom = c_tier

        # If no STT transcripts available at all, skip gracefully
        if not state.stt_transcripts:
            logger.warning("[Agent 3.5] No STT transcripts available. Skipping deep analysis.")
            return state

        raw_map = {p.get("post_id", ""): p for p in state.raw_posts}

        def build_entry(scored: Dict, category: str) -> Dict[str, Any]:
            pid = scored.get("post_id", "")
            raw = raw_map.get(pid, {})
            return {
                "post_id":   pid,
                "tier":      scored.get("tier"),
                "score":     scored.get("total_score", 0),
                "views":     raw.get("views") or raw.get("view_count", 0),
                "likes":     raw.get("likes") or raw.get("like_count", 0),
                "transcript": state.stt_transcripts.get(pid, "")[:1500],
            }

        top_data    = [build_entry(s, "top")    for s in targets_top    if state.stt_transcripts.get(s.get("post_id", ""))]
        bottom_data = [build_entry(s, "bottom") for s in targets_bottom if state.stt_transcripts.get(s.get("post_id", ""))]

        if not top_data and not bottom_data:
            logger.warning("[Agent 3.5] No transcripts matched top/bottom posts. Skipping.")
            return state

        state.update_progress("deep_analyze", 68,
            f"Structural comparison: {len(top_data)} top + {len(bottom_data)} bottom clips with transcripts...")

        user_msg = (
            f"Client: @{state.account_handle} on {state.platform}\n"
            f"=== TOP PERFORMING CLIPS ({len(top_data)}) WITH TRANSCRIPTS ===\n"
            f"{json.dumps(top_data, default=str)}\n\n"
            f"=== BOTTOM PERFORMING CLIPS ({len(bottom_data)}) WITH TRANSCRIPTS ===\n"
            f"{json.dumps(bottom_data, default=str)}"
        )

        state.update_progress("deep_analyze", 70, "Running deep structural LLM analysis...")
        try:
            deep_result = self._llm.generate_json(
                system_prompt=DEEP_ANALYSIS_SYSTEM_PROMPT,
                user_message=user_msg,
                temperature=0.25,
                max_tokens=2500,
            )
            if deep_result and isinstance(state.account_dna, dict):
                state.account_dna["deep_stt_structural_insights"] = deep_result
                logger.info("[Agent 3.5] Deep STT structural insights added to Account DNA.")
        except Exception as e:
            logger.warning(f"[Agent 3.5] Deep analysis LLM call failed: {e}")
            state.deep_analysis_errors.append(str(e))

        state.deep_analysis_completed = True
        return state
