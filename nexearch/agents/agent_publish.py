"""
Nexearch — Agent 6: Publisher Agent
Handles publishing via configured method (Metricool, Platform API, Crawlee).
Generates platform-specific titles, captions, descriptions via Nex Agent integration.
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from loguru import logger

from nexearch.agents.state import PipelineState
from nexearch.tools.llm_router import get_nexearch_llm
from nexearch.tools.publishers.publisher import create_publisher, PublishResult


WRITING_SYSTEM_PROMPT = """You are Nex Agent — an enterprise-grade social media copywriter.
Write the {content_type} for a {platform} post based on the following directive and content.

Client DNA Summary: {dna_summary}
Writing Directive: {writing_directive}
Tone: {tone}

CRITICAL RULES:
- Match the client's voice and style exactly
- Follow the platform's best practices for {platform}
- Make it engaging, authentic, and on-brand
- {platform_specific_rules}

Content Context:
{content_context}

RETURN ONLY the {content_type} text, nothing else."""


PLATFORM_RULES = {
    "instagram": "Max 2200 chars. Use line breaks for readability. Hashtags at end. Strong CTA.",
    "tiktok": "Keep it short and punchy. Max 150 chars for on-screen text. Trending hashtags.",
    "youtube": "SEO-optimized. Include keywords. Max 100 chars title, 5000 chars desc. Timestamps in desc.",
    "twitter": "Max 280 chars. No hashtag spam. Provocative or insightful. Thread-worthy.",
    "linkedin": "Professional tone. Industry keywords. Thought leadership style. 1-3 hashtags.",
    "facebook": "Conversational. Ask questions. Share-worthy. 1-2 sentences for title.",
}


class PublisherAgent:
    """
    Agent 6 — Publisher
    Generates platform-specific content and publishes via configured method.
    """

    NAME = "publisher_agent"

    def __init__(self):
        self._llm = get_nexearch_llm()

    async def run(self, state: PipelineState) -> PipelineState:
        """Generate content and publish (or queue for approval)."""
        logger.info("[Agent 6] Publisher Agent starting")
        state.update_progress("publish", 80, "Preparing content for publishing...")

        if state.skip_publish:
            state.update_progress("publish", 95, "Publishing skipped (analysis-only mode)")
            return state

        if not state.clip_directive:
            state.add_error("No ClipDirective available for publishing")
            return state

        try:
            # Generate writing content
            writing = await self._generate_writing(state)
            publish_asset = self._resolve_publish_asset(state)

            if state.dry_run:
                state.published_posts.append({
                    "status": "dry_run",
                    "title": writing.get("title", ""),
                    "caption": writing.get("caption", ""),
                    "description": writing.get("description", ""),
                    "hashtags": writing.get("hashtags", []),
                    "directive_id": state.directive_id,
                })
                state.update_progress("publish", 95, "Dry run complete — content generated")
                return state

            if not publish_asset:
                state.publish_errors.append("Publish stage skipped: no media asset was provided for this pipeline run")
                state.update_progress("publish", 92, "Publish skipped — awaiting media asset")
                logger.info("[Agent 6] Publish skipped because no media asset was provided")
                return state

            platform_creds = state.get_creds_for_platform(state.platform)

            # Create publisher
            publisher = create_publisher(
                method=state.publishing_method,
                platform=state.platform,
                client_id=state.client_id,
                **platform_creds,
            )

            if not await publisher.check_availability():
                state.publish_errors.append(
                    f"Publishing backend '{state.publishing_method}' is not available for {state.platform}"
                )
                state.update_progress("publish", 92, "Publish skipped — backend unavailable")
                logger.warning("[Agent 6] Publishing backend unavailable")
                return state

            result = await publisher.publish(
                video_url=publish_asset,
                caption=writing.get("caption", ""),
                title=writing.get("title", ""),
                description=writing.get("description", ""),
                hashtags=writing.get("hashtags", []),
                credentials=platform_creds,
            )

            if result.success:
                state.published_posts.append({
                    "status": "published",
                    "title": writing.get("title", ""),
                    "caption": writing.get("caption", ""),
                    "description": writing.get("description", ""),
                    "hashtags": writing.get("hashtags", []),
                    "directive_id": state.directive_id,
                    "publish_method": state.publishing_method,
                    "publish_id": result.platform_post_id or result.metricool_post_id or str(uuid.uuid4()),
                    "platform_post_url": result.platform_post_url,
                    "platform": state.platform,
                    "video_url": publish_asset,
                    "raw_response": result.raw_response,
                })
                state.update_progress("publish", 95, "Content published successfully")
                logger.info("[Agent 6] Content published successfully")
            else:
                error_message = result.error_message or "Publishing failed"
                state.publish_errors.append(error_message)
                state.update_progress("publish", 92, "Publish attempted but failed")
                logger.warning(f"[Agent 6] Publish failed: {error_message}")

        except Exception as e:
            state.add_error(f"Publisher failed: {e}")
            logger.error(f"[Agent 6] Error: {e}")

        return state

    def _resolve_publish_asset(self, state: PipelineState) -> str:
        """Resolve the media asset to publish from the directive payload."""
        candidates = [
            state.clip_directive.get("video_url"),
            state.clip_directive.get("media_url"),
            state.clip_directive.get("asset_url"),
            state.clip_directive.get("source_video_url"),
            (state.clip_directive.get("publish_payload", {}) or {}).get("video_url"),
            (state.clip_directive.get("publish_payload", {}) or {}).get("asset_url"),
        ]

        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return ""

    async def _generate_writing(self, state: PipelineState) -> Dict[str, str]:
        """Generate title, caption, and description using Nex Agent writing skills."""
        directive = state.clip_directive
        dna = state.account_dna
        writing_directives = directive.get("writing_directives", {})
        dna_summary = dna.get("content_dna_summary", "")
        tone = writing_directives.get("tone_guide", "")
        platform_rules = PLATFORM_RULES.get(state.platform, "")
        content_context = f"Account: @{state.account_handle}\nDNA Summary: {dna_summary}"
        extra_context = directive.get("content_context", "") or directive.get("source_context", "")
        if extra_context:
            content_context += f"\n\nClip Context:\n{extra_context}"

        result = {}

        # Generate title for all platforms so short-form uploads can lead with a strong hook.
        result["title"] = self._write(
            "title", state.platform, dna_summary,
            writing_directives.get("title_directive", ""),
            tone, platform_rules, content_context,
        )

        # Generate caption
        result["caption"] = self._write(
            "caption", state.platform, dna_summary,
            writing_directives.get("caption_directive", ""),
            tone, platform_rules, content_context,
        )

        # Generate description (for YouTube, Facebook, LinkedIn)
        if state.platform in ("youtube", "facebook", "linkedin"):
            result["description"] = self._write(
                "description", state.platform, dna_summary,
                writing_directives.get("description_directive", ""),
                tone, platform_rules, content_context,
            )

        # Generate hashtags
        hashtag_text = self._write(
            "hashtags (return comma-separated list only)", state.platform, dna_summary,
            writing_directives.get("hashtag_directive", ""),
            tone, platform_rules, content_context,
        )
        result["hashtags"] = [h.strip().lstrip("#") for h in hashtag_text.split(",") if h.strip()]

        return result

    def _write(self, content_type, platform, dna_summary, directive, tone, rules, context) -> str:
        """Generate a piece of content using LLM."""
        system = WRITING_SYSTEM_PROMPT.format(
            content_type=content_type, platform=platform, dna_summary=dna_summary,
            writing_directive=directive or "Write naturally based on the DNA",
            tone=tone or "authentic and engaging",
            platform_specific_rules=rules, content_context=context,
        )
        try:
            return self._llm.generate(
                system_prompt=system, user_message=f"Generate the {content_type} now.",
                temperature=0.5, max_tokens=2000,
            ).strip()
        except Exception as e:
            logger.warning(f"Writing generation failed for {content_type}: {e}")
            return ""
