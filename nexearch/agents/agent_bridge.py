"""
Nexearch — Agent 5: NexClip Bridge Agent
Converts Account DNA into a ClipDirective for NexClip consumption.
Generates the system prompt injection for NexClip's AI pipeline.
"""

import json
import uuid
from typing import Dict, Any
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.llm_router import get_nexearch_llm


BRIDGE_SYSTEM_PROMPT = """You are Nexearch Bridge — you translate Account DNA into NexClip ClipDirectives.
Given the Account DNA and evolution data, generate a complete ClipDirective.

Also generate a SYSTEM PROMPT INJECTION — a plain English paragraph (200-400 words) that will be
injected at the top of NexClip's AI processing prompt. This must capture:
- What kind of content this account creates
- The tone, style, and pacing that works best
- Topics to focus on and avoid
- Writing style for titles, captions, and descriptions
- Hook strategies that work
- Audience psychology and engagement patterns

Also generate WRITING DIRECTIVES — specific instructions for the Nex Agent on how to write
titles, captions, and descriptions for this specific client.

RETURN ONLY VALID JSON:
{{
  "clip_parameters": {{
    "target_length_seconds": 38,
    "min_length_seconds": 25,
    "max_length_seconds": 55,
    "pacing_style": "fast_cut|medium|slow_build",
    "preferred_format": "talking_head|slideshow|screen_share|montage"
  }},
  "hook_directive": {{
    "required_hook_type": "",
    "alternative_hook_types": [],
    "max_hook_duration_seconds": 4,
    "hook_rewrite_instruction": ""
  }},
  "content_directive": {{
    "prioritize_topics": [],
    "avoid_topics": [],
    "emotional_tone_target": "",
    "audience_description": "",
    "identity_language": ""
  }},
  "avoid_directive": {{
    "avoid_hook_types": [],
    "avoid_slow_intros_over_seconds": 3,
    "avoid_topics": [],
    "avoid_caption_patterns": []
  }},
  "writing_directives": {{
    "title_directive": "how to write titles for this client",
    "caption_directive": "how to write captions",
    "description_directive": "how to write descriptions",
    "hashtag_directive": "hashtag strategy",
    "tone_guide": "tone and voice guide",
    "vocabulary_guide": "vocabulary preferences"
  }},
  "nexclip_system_prompt_injection": "200-400 word plain English context..."
}}"""


class NexClipBridgeAgent:
    """
    Agent 5 — NexClip Bridge
    Converts DNA + evolution data into a ClipDirective.
    """

    NAME = "nexclip_bridge_agent"

    def __init__(self):
        self._llm = get_nexearch_llm()

    async def run(self, state: PipelineState) -> PipelineState:
        """Generate ClipDirective and system prompt injection."""
        logger.info("[Agent 5] NexClip Bridge starting")
        state.update_progress("bridge", 72, "Generating ClipDirective...")

        if not state.account_dna:
            state.add_error("Cannot bridge without Account DNA")
            return state

        try:
            evolution_payload = state.evolution_changes
            if not evolution_payload and state.platform_evolution:
                evolution_payload = [
                    {"platform": platform, **payload}
                    for platform, payload in state.platform_evolution.items()
                    if payload
                ]

            user_msg = (
                f"Account: @{state.account_handle} on {state.platform}\n"
                f"Account DNA:\n{json.dumps(state.account_dna, default=str)[:6000]}\n\n"
                f"Tier Distribution: {json.dumps(state.tier_distribution)}\n"
                f"Evolution Changes: {json.dumps(evolution_payload, default=str)[:2000]}"
            )

            directive = self._llm.generate_json(
                system_prompt=BRIDGE_SYSTEM_PROMPT, user_message=user_msg,
                temperature=0.3, max_tokens=6000,
            )

            if directive:
                state.clip_directive = directive
                state.directive_id = str(uuid.uuid4())
                state.nexclip_system_prompt = directive.get("nexclip_system_prompt_injection", "")

                state.update_progress("bridge", 78, "ClipDirective generated")
                logger.info(f"[Agent 5] Directive generated: {state.directive_id}")
            else:
                state.add_error("ClipDirective generation returned empty")

        except Exception as e:
            state.add_error(f"Bridge failed: {e}")
            logger.error(f"[Agent 5] Error: {e}")

        return state
