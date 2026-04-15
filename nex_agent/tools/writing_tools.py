"""
Nex Agent — Enterprise Writing Tools for Nexearch
=====================================================
Post writing, title writing, description writing for all 7 platforms.
Called by Nexearch's Publisher Agent via the command bus or direct invocation.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

logger = logging.getLogger("nex_agent.tools.writing")


# ── Platform-Specific Writing Prompts ──────────────────────────

PLATFORM_WRITING_SPECS = {
    "instagram": {
        "title_max": 0,  # IG doesn't use titles
        "caption_max": 2200,
        "description_max": 0,
        "hashtag_limit": 30,
        "best_caption_length": "150-250 chars for engagement, up to 2200 for storytelling",
        "style": "Conversational, relatable, emoji-rich. Hook in first line (before 'more'). CTA at end. Hashtags: mix of niche + trending.",
        "restrictions": "No clickable links in captions. Use 'link in bio' CTA.",
    },
    "tiktok": {
        "title_max": 0,
        "caption_max": 4000,
        "description_max": 0,
        "hashtag_limit": 5,
        "best_caption_length": "50-150 chars. Short, punchy. Let the video do the talking.",
        "style": "Gen-Z language, trending sounds references, challenge hooks. Short + viral. Minimal hashtags (3-5 targeted).",
        "restrictions": "Captions are secondary to video. Keep concise.",
    },
    "youtube": {
        "title_max": 100,
        "caption_max": 0,
        "description_max": 5000,
        "hashtag_limit": 15,
        "best_caption_length": "N/A",
        "style": "SEO-optimized titles (60-70 chars ideal). Descriptions: first 2 lines visible, rest below fold. Timestamps, links, hashtags in description.",
        "restrictions": "Titles must be searchable. Avoid clickbait that doesn't deliver.",
    },
    "linkedin": {
        "title_max": 0,
        "caption_max": 3000,
        "description_max": 2000,
        "hashtag_limit": 5,
        "best_caption_length": "1200-2000 chars. Professional thought leadership.",
        "style": "Professional, insightful, data-driven. Open with a bold statement or stat. Line breaks for readability. 3-5 relevant hashtags. CTA for engagement (agree/disagree?).",
        "restrictions": "No informal slang. Maintain professional tone.",
    },
    "twitter": {
        "title_max": 0,
        "caption_max": 280,
        "description_max": 0,
        "hashtag_limit": 3,
        "best_caption_length": "Under 280 chars. Threading for long-form.",
        "style": "Sharp, witty, quotable. Hook immediately. Max 1-3 hashtags. Controversial takes perform well. Quote-tweet bait.",
        "restrictions": "Hard 280 char limit. No multi-paragraph.",
    },
    "facebook": {
        "title_max": 255,
        "caption_max": 63206,
        "description_max": 5000,
        "hashtag_limit": 10,
        "best_caption_length": "40-80 chars for engagement, up to 500 for storytelling.",
        "style": "Community-driven, shareable, emotional. Questions perform well. Longer captions OK for storytelling. Moderate hashtag use.",
        "restrictions": "Avoid engagement bait (Facebook penalizes 'tag a friend' type CTAs).",
    },
}

WRITING_SYSTEM_PROMPT = """You are Nex Agent's Enterprise Writing Engine — the most advanced social media copy system.

Your writing is:
- Platform-native (sounds like a top creator ON that specific platform)
- Data-driven (based on Account DNA and winning patterns)
- Psychologically optimized (hooks, curiosity gaps, CTAs, social proof)
- SEO-aware (for YouTube/LinkedIn especially)
- Brand-consistent (matching the client's established voice)

NEVER produce generic, template-sounding copy. Each piece must feel hand-crafted.

Platform specs:
{platform_specs}

Client DNA context:
{client_context}

Writing DNA:
{writing_dna}
"""


def _write_post_title(platform: str, topic: str, client_dna: str = "{}",
                       writing_dna: str = "{}",
                       additional_context: str = "") -> Dict[str, Any]:
    """Generate an enterprise-grade title for a post."""
    from nex_agent.llm_provider import get_llm_provider

    specs = PLATFORM_WRITING_SPECS.get(platform, PLATFORM_WRITING_SPECS["instagram"])

    if specs["title_max"] == 0 and platform not in ("youtube", "facebook"):
        return {"title": "", "note": f"{platform} doesn't use separate titles"}

    system = WRITING_SYSTEM_PROMPT.format(
        platform_specs=json.dumps(specs, indent=2),
        client_context=client_dna[:2000],
        writing_dna=writing_dna[:1500],
    )

    user_msg = f"""Generate 5 title options for {platform}.

Topic/Hook: {topic}
{f'Additional context: {additional_context}' if additional_context else ''}

Requirements:
- Max {specs['title_max']} characters each
- SEO-optimized for {platform}
- Ranked by predicted engagement (best first)
- Include a mix of: curiosity gap, how-to, number-based, emotional

RETURN JSON:
{{"titles": [{{"title": "", "type": "curiosity|howto|number|emotional", "char_count": 0, "seo_keywords": []}}], "recommended": 0}}"""

    llm = get_llm_provider()
    response = llm.chat(system_prompt=system, user_message=user_msg,
                         temperature=0.7, max_tokens=2000)

    try:
        result = json.loads(response) if isinstance(response, str) else response
    except (json.JSONDecodeError, TypeError):
        result = {"titles": [{"title": response, "type": "generated"}], "recommended": 0}

    return {"platform": platform, "result": result}


def _write_post_caption(platform: str, topic: str, client_dna: str = "{}",
                          writing_dna: str = "{}",
                          hook_style: str = "auto",
                          include_hashtags: bool = True,
                          include_cta: bool = True,
                          tone: str = "auto") -> Dict[str, Any]:
    """Generate an enterprise-grade caption/post text."""
    from nex_agent.llm_provider import get_llm_provider

    specs = PLATFORM_WRITING_SPECS.get(platform, PLATFORM_WRITING_SPECS["instagram"])
    system = WRITING_SYSTEM_PROMPT.format(
        platform_specs=json.dumps(specs, indent=2),
        client_context=client_dna[:2000],
        writing_dna=writing_dna[:1500],
    )

    user_msg = f"""Generate 3 caption/post text options for {platform}.

Topic: {topic}
Hook style: {hook_style}
Include hashtags: {include_hashtags}
Include CTA: {include_cta}
Tone override: {tone}

Best length: {specs['best_caption_length']}
Max chars: {specs['caption_max']}
Max hashtags: {specs['hashtag_limit']}
Style guide: {specs['style']}
Restrictions: {specs['restrictions']}

RETURN JSON:
{{"captions": [{{"caption": "", "hook_type": "", "cta_type": "", "hashtags": [], "char_count": 0, "engagement_prediction": "high|medium|low"}}], "recommended": 0}}"""

    llm = get_llm_provider()
    response = llm.chat(system_prompt=system, user_message=user_msg,
                         temperature=0.7, max_tokens=3000)

    try:
        result = json.loads(response) if isinstance(response, str) else response
    except (json.JSONDecodeError, TypeError):
        result = {"captions": [{"caption": response}], "recommended": 0}

    return {"platform": platform, "result": result}


def _write_post_description(platform: str, topic: str, title: str = "",
                              client_dna: str = "{}",
                              writing_dna: str = "{}",
                              include_timestamps: bool = False,
                              include_links: bool = True) -> Dict[str, Any]:
    """Generate enterprise-grade description (mainly YouTube, Facebook, LinkedIn)."""
    from nex_agent.llm_provider import get_llm_provider

    if platform not in ("youtube", "facebook", "linkedin"):
        return {"description": "", "note": f"{platform} doesn't use separate descriptions"}

    specs = PLATFORM_WRITING_SPECS.get(platform, {})
    system = WRITING_SYSTEM_PROMPT.format(
        platform_specs=json.dumps(specs, indent=2),
        client_context=client_dna[:2000],
        writing_dna=writing_dna[:1500],
    )

    user_msg = f"""Generate a full description for {platform}.

Title: {title}
Topic: {topic}
Include timestamps: {include_timestamps}
Include links section: {include_links}

Platform style: {specs.get('style', '')}
Max length: {specs.get('description_max', 5000)} chars

Structure:
1. First 2 lines: compelling summary (visible above fold)
2. Full description with key points
3. {'Timestamps section' if include_timestamps else ''}
4. {'Related links section' if include_links else ''}
5. Hashtags (max {specs.get('hashtag_limit', 10)})

RETURN JSON:
{{"description": "", "above_fold_text": "", "hashtags": [], "char_count": 0, "seo_keywords": []}}"""

    llm = get_llm_provider()
    response = llm.chat(system_prompt=system, user_message=user_msg,
                         temperature=0.6, max_tokens=4000)

    try:
        result = json.loads(response) if isinstance(response, str) else response
    except (json.JSONDecodeError, TypeError):
        result = {"description": response}

    return {"platform": platform, "result": result}


def _write_full_post_package(platform: str, topic: str, client_dna: str = "{}",
                               writing_dna: str = "{}") -> Dict[str, Any]:
    """Generate a complete post package: title + caption + description + hashtags."""
    title_result = _write_post_title(platform, topic, client_dna, writing_dna)
    caption_result = _write_post_caption(platform, topic, client_dna, writing_dna)
    desc_result = _write_post_description(
        platform, topic,
        title=title_result.get("result", {}).get("titles", [{}])[0].get("title", ""),
        client_dna=client_dna, writing_dna=writing_dna,
    )

    return {
        "platform": platform,
        "topic": topic,
        "title": title_result,
        "caption": caption_result,
        "description": desc_result,
        "package_complete": True,
    }


def _analyze_writing_quality(text: str, platform: str) -> Dict[str, Any]:
    """Analyze the quality of existing copy for a platform."""
    from nex_agent.llm_provider import get_llm_provider

    specs = PLATFORM_WRITING_SPECS.get(platform, {})
    prompt = f"""Analyze this {platform} post text and score it:

Text: {text[:3000]}

Score each dimension 1-10:
1. Hook strength (does it grab attention immediately?)
2. CTA effectiveness (does it drive action?)
3. Platform-nativeness (does it sound natural for {platform}?)
4. Engagement potential (will people comment/share?)
5. SEO quality (for searchable platforms)
6. Emotional resonance
7. Readability

Platform specs: {json.dumps(specs, indent=2)}

RETURN JSON:
{{"scores": {{"hook": 0, "cta": 0, "platform_native": 0, "engagement": 0, "seo": 0, "emotion": 0, "readability": 0}}, "overall": 0, "strengths": [], "weaknesses": [], "improvement_suggestions": []}}"""

    llm = get_llm_provider()
    response = llm.chat(system_prompt="You are a writing quality analyst.", user_message=prompt)

    try:
        return json.loads(response) if isinstance(response, str) else response
    except (json.JSONDecodeError, TypeError):
        return {"overall": 5, "note": "Analysis parsing failed"}


def _get_platform_writing_specs(platform: str = "all") -> Dict[str, Any]:
    """Get writing specifications for a platform."""
    if platform == "all":
        return {"platforms": PLATFORM_WRITING_SPECS}
    return PLATFORM_WRITING_SPECS.get(platform, {"error": f"Unknown platform: {platform}"})


# ── Registration ───────────────────────────────────────────────

def register(executor: "ToolExecutor") -> int:
    """Register all enterprise writing tools."""
    tools = [
        ("write_post_title", "Generate enterprise-grade post titles for any platform (YouTube, Facebook, etc). Returns 5 ranked options with SEO keywords.", _write_post_title,
         {"type": "object", "properties": {"platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"]}, "topic": {"type": "string"}, "client_dna": {"type": "string", "default": "{}"}, "writing_dna": {"type": "string", "default": "{}"}, "additional_context": {"type": "string", "default": ""}}, "required": ["platform", "topic"]}),

        ("write_post_caption", "Generate enterprise-grade post caption/text for any platform. Returns 3 options with hooks, CTAs, and hashtags.", _write_post_caption,
         {"type": "object", "properties": {"platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"]}, "topic": {"type": "string"}, "client_dna": {"type": "string", "default": "{}"}, "writing_dna": {"type": "string", "default": "{}"}, "hook_style": {"type": "string", "default": "auto"}, "include_hashtags": {"type": "boolean", "default": True}, "include_cta": {"type": "boolean", "default": True}, "tone": {"type": "string", "default": "auto"}}, "required": ["platform", "topic"]}),

        ("write_post_description", "Generate enterprise-grade description for YouTube, Facebook, or LinkedIn. Includes above-fold text, timestamps, links, hashtags.", _write_post_description,
         {"type": "object", "properties": {"platform": {"type": "string", "enum": ["youtube", "facebook", "linkedin"]}, "topic": {"type": "string"}, "title": {"type": "string", "default": ""}, "client_dna": {"type": "string", "default": "{}"}, "writing_dna": {"type": "string", "default": "{}"}, "include_timestamps": {"type": "boolean", "default": False}, "include_links": {"type": "boolean", "default": True}}, "required": ["platform", "topic"]}),

        ("write_full_post_package", "Generate a complete post package (title + caption + description + hashtags) for any platform in one call.", _write_full_post_package,
         {"type": "object", "properties": {"platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"]}, "topic": {"type": "string"}, "client_dna": {"type": "string", "default": "{}"}, "writing_dna": {"type": "string", "default": "{}"}}, "required": ["platform", "topic"]}),

        ("analyze_writing_quality", "Analyze the quality of existing post text for a platform. Scores hook, CTA, engagement, SEO, emotion, readability.", _analyze_writing_quality,
         {"type": "object", "properties": {"text": {"type": "string"}, "platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"]}}, "required": ["text", "platform"]}),

        ("get_platform_writing_specs", "Get writing specifications and best practices for a platform (char limits, style guides, restrictions).", _get_platform_writing_specs,
         {"type": "object", "properties": {"platform": {"type": "string", "default": "all"}}, "required": []}),
    ]

    for name, desc, handler, params in tools:
        executor.register(name=name, description=desc, category="writing",
                          handler=handler, parameters=params)

    return len(tools)
