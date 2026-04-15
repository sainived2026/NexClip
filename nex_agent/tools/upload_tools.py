"""
Nex Agent — Upload Workflow Tools
====================================
High-level orchestration tools for the full clip upload pipeline:
search project → get clips → apply captions → generate title/description → hand to Arc Agent.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

from loguru import logger


def _get_storage_root() -> Path:
    """Get the absolute path to the NexClip storage root."""
    root = os.environ.get("STORAGE_LOCAL_ROOT", "./storage")
    base = Path(__file__).resolve().parent.parent.parent / "backend"
    p = (base / root).resolve()
    if p.exists():
        return p
    alt = Path(__file__).resolve().parent.parent.parent / "backend" / "storage"
    alt.mkdir(parents=True, exist_ok=True)
    return alt


async def _upload_via_arc_agent(
    clips: List[Dict[str, Any]],
    platform: str,
    method: str,  # "playwright", "metricool", "platform_api"
    title: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """Send upload request to Arc Agent via the bridge."""
    import httpx

    arc_url = os.environ.get("ARC_AGENT_URL", "http://localhost:8003")
    payload = {
        "message": (
            f"Upload {len(clips)} clips to {platform} using {method}. "
            f"Title: {title or 'auto-generate'}. "
            f"Description: {description or 'auto-generate'}. "
            f"Clip paths: {json.dumps([c['absolute_path'] for c in clips])}"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{arc_url}/api/chat", json=payload)
            return resp.json()
    except Exception as e:
        return {"error": f"Arc Agent communication failed: {e}"}


def _apply_caption_to_clip(
    clip_path: str, caption_style: str, project_id: str
) -> Dict[str, Any]:
    """Apply a caption style to a clip via the backend HTTP API.

    Nex Agent runs in a separate process from the backend, so we CANNOT
    access the backend's SQLite DB directly. Instead we use the project
    API to find the clip ID, then call the caption render endpoint.
    """
    try:
        import httpx

        backend_url = os.environ.get("NEXCLIP_BACKEND_URL", "http://localhost:8000")

        # Get auth token for API calls
        token = ""
        try:
            from nex_agent.tools.video_tools import _get_auth_token
            token = _get_auth_token()
        except Exception:
            pass

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Step 1: Get project data to find the clip ID
        resp = httpx.get(f"{backend_url}/api/projects/{project_id}", headers=headers, timeout=15)
        if resp.status_code != 200:
            return {"error": f"Project lookup failed: {resp.status_code}"}

        project_data = resp.json()
        clips = project_data.get("clips", [])

        # Find matching clip by file_path
        clip_id = None
        for c in clips:
            c_path = c.get("file_path", "")
            if c_path and (c_path == clip_path or clip_path.endswith(c_path) or c_path.endswith(clip_path)):
                clip_id = c.get("id", "")
                break

        if not clip_id:
            return {"error": f"Clip not found for path: {clip_path}"}

        # Step 2: Trigger caption rendering via the actual API endpoint
        headers["Content-Type"] = "application/json"
        resp = httpx.post(
            f"{backend_url}/api/clips/{clip_id}/apply-caption-style",
            json={"style_id": caption_style, "active_aspect": "9:16"},
            headers=headers,
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            return {"error": f"Caption API returned {resp.status_code}: {resp.text[:200]}"}

    except Exception as e:
        return {"error": f"Caption application failed: {e}"}


def _generate_title_description(
    project_id: str, clip_info: List[Dict], platform: str = "instagram",
) -> Dict[str, str]:
    """
    Generate enterprise-grade title and description from video summary using LLM.
    Uses platform-specific optimization with deep algorithm awareness.
    """

    # ── Enterprise System Prompt ──────────────────────────────
    TITLE_DESC_SYSTEM_PROMPT = """You are NexClip's Content Intelligence Engine — a world-class social media copywriter 
with deep expertise in platform algorithms, audience psychology, and viral content mechanics.

═══════════════════════════════════════════════════════════════
ROLE & MISSION
═══════════════════════════════════════════════════════════════
You generate optimized titles and descriptions for short-form video clips 
that are about to be published to social media platforms. Your goal is to 
MAXIMIZE reach, engagement (likes, comments, shares, saves), and watch-through rate.

You are given:
  1. A summary of the original video the clips were generated from
  2. The individual clip titles and hooks
  3. The target platform

You MUST return valid JSON with exactly two keys: "title" and "description".

═══════════════════════════════════════════════════════════════
PLATFORM-SPECIFIC INTELLIGENCE
═══════════════════════════════════════════════════════════════

### INSTAGRAM (Reels)
- Title: 40-80 chars. First 2 words must be a HOOK. Use power words: "This", "Wait", "Why", "How", "POV"
- Description (Caption): 150-500 chars. Use 2-3 lines max before "more". Include CTA ("Save this", "Tag someone", "Follow for more")
- Hashtags: 3-5 niche-specific hashtags at the END (NOT in title). Mix popular + niche
- Algorithm priority: Watch time > Saves > Shares > Comments > Likes
- Avoid: Clickbait that doesn't deliver, walls of text, generic hashtags like #viral #fyp

### TIKTOK
- Title: 30-60 chars. Pattern interrupt first ("Wait for it", "Nobody talks about this"). Use ALL CAPS for 1-2 words
- Description: 100-300 chars. Conversational, Gen-Z friendly tone. Use "you" language
- Hashtags: 2-4 highly specific hashtags (NOT #fyp #foryou — TikTok ignores them)
- Algorithm priority: Completion rate > Rewatches > Shares > Profile visits
- Avoid: Formal language, corporate tone, more than 4 hashtags

### YOUTUBE (Shorts)
- Title: 50-100 chars. Must include a searchable keyword. Curiosity gap format ("I tried X for 30 days")
- Description: 200-500 chars. Include 1-2 relevant keywords naturally. Add a CTA to subscribe
- Hashtags: #Shorts is required. Add 1-2 topic hashtags
- Algorithm priority: Click-through rate > Watch time > Engagement
- Avoid: Misleading titles, ALL CAPS spam, keyword stuffing

### LINKEDIN
- Title: Not traditionally used — put hook as first line of description
- Description: 200-600 chars. Professional, insight-driven tone. Open with a bold statement or statistic
  Then briefly describe the value. End with a question to drive comments
- Hashtags: 3-5 professional/industry hashtags
- Algorithm priority: Dwell time > Comments > Shares > Reactions
- Avoid: Casual language, emoji-heavy content, sales pitch tone

### TWITTER / X
- Title: 30-50 chars. Ultra-concise. Tweet-style hook
- Description: 100-280 chars (tweet limit). Punchy, opinionated. Drive retweets with controversy or insight
- Hashtags: 1-2 MAX (Twitter penalizes hashtag spam)
- Algorithm priority: Replies > Retweets > Bookmarks > Likes
- Avoid: More than 2 hashtags, walls of text, corporate-speak

### FACEBOOK
- Title: 40-80 chars. Emotional or relatable hook. "This is why..." patterns work well
- Description: 150-400 chars. Storytelling tone. Ask a question. Use short paragraphs
- Hashtags: 1-3 relevant hashtags
- Algorithm priority: Meaningful interactions > Shares > Comments > Watch time
- Avoid: Engagement bait ("Tag 3 friends"), link-heavy posts, generic content

═══════════════════════════════════════════════════════════════
COPYWRITING RULES (NON-NEGOTIABLE)
═══════════════════════════════════════════════════════════════

1. HOOK FIRST — The first 5 words determine if someone stops scrolling. Make them count.
   Good: "Nobody teaches you THIS about..."
   Bad: "In this video we discuss..."

2. CURIOSITY GAP — Create a knowledge gap that can only be filled by watching.
   Good: "I changed ONE thing and got 10x results"
   Bad: "How to get better results"

3. SPECIFICITY WINS — Specific numbers, timeframes, and details outperform vague claims.
   Good: "This 3-second trick saves $500/month"
   Bad: "Money-saving tips"

4. EMOTIONAL TRIGGERS — Use at least one: surprise, curiosity, fear of missing out, aspiration, humor, controversy.

5. POWER WORDS — Incorporate from this list when natural:
   Urgency: "Now", "Before it's too late", "Don't miss"
   Curiosity: "Secret", "Hidden", "Nobody knows"
   Value: "Free", "Proven", "Guaranteed"
   Social proof: "Everyone's talking about", "Millions", "Trending"

6. CTA (Call to Action) — Every description must end with a clear CTA.
   Save-focused: "Save this for later"
   Follow-focused: "Follow for daily tips"
   Comment-focused: "What's your experience? Drop it below"
   Share-focused: "Send this to someone who needs it"

7. NO FILLER — Every word must earn its place. Cut: "In this video", "Hey guys", "Let me tell you"

8. AUTHENTICITY — Sound like a human, not a brand. Match the energy of the video content.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRICT)
═══════════════════════════════════════════════════════════════

Return ONLY valid JSON:
{
  "title": "Your platform-optimized title here",
  "description": "Your platform-optimized description with hashtags here"
}

Do NOT include markdown, explanations, or anything outside the JSON object.
The title and description must be ready to publish AS-IS — no placeholders, no [insert here]."""

    try:
        import sys
        backend_path = str(Path(__file__).resolve().parent.parent.parent / "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        from app.services.llm_service import LLMService
        from app.db.database import SessionLocal
        from app.db.models import Project

        db = SessionLocal()
        try:
            proj = db.query(Project).filter(Project.id == project_id).first()
            project_title = proj.title if proj else "Untitled"
        finally:
            db.close()

        # Load summary if available
        safe_title = re.sub(r'[\\/*?:"<>| ]', '_', project_title)
        folder = f"{safe_title}_{project_id[:8]}"
        summary_path = _get_storage_root() / folder / "summary" / "summary.json"

        summary_text = ""
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                summary_text = data.get("summary", "")

        clip_titles = [c.get("title_suggestion", "") for c in clip_info if c.get("title_suggestion")]
        clip_hooks = [c.get("hook_text", "") for c in clip_info if c.get("hook_text")]
        clip_scores = [c.get("viral_score", 0) for c in clip_info]

        user_prompt = (
            f"Generate an optimized title and description for publishing to **{platform.upper()}**.\n\n"
            f"━━━ VIDEO CONTEXT ━━━\n"
            f"Project Name: {project_title}\n"
            f"Video Summary: {summary_text or 'Not available — use clip titles and hooks for context.'}\n\n"
            f"━━━ CLIP INTELLIGENCE ━━━\n"
            f"Number of clips being uploaded: {len(clip_info)}\n"
            f"Clip titles: {clip_titles or ['No titles available']}\n"
            f"Clip hooks: {clip_hooks or ['No hooks available']}\n"
            f"Viral scores: {clip_scores}\n"
            f"Best clip score: {max(clip_scores) if clip_scores else 'N/A'}\n\n"
            f"━━━ INSTRUCTIONS ━━━\n"
            f"Write for {platform.upper()} specifically. Follow all platform rules from your system prompt.\n"
            f"Match the tone and energy of the video content.\n"
            f"Return ONLY the JSON object with 'title' and 'description'."
        )

        llm = LLMService()
        response = llm.generate(
            system_prompt=TITLE_DESC_SYSTEM_PROMPT,
            user_message=user_prompt,
        )

        # Parse JSON from response (robust extraction)
        try:
            # Try full response as JSON first
            result = json.loads(response.strip())
            return {
                "title": result.get("title", project_title),
                "description": result.get("description", ""),
            }
        except json.JSONDecodeError:
            pass

        try:
            # Try to find JSON block in response
            json_match = re.search(r'\{[^{}]*"title"[^{}]*"description"[^{}]*\}', response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "title": result.get("title", project_title),
                    "description": result.get("description", ""),
                }
        except Exception:
            pass

        return {"title": project_title, "description": summary_text[:500] if summary_text else ""}

    except Exception as e:
        logger.error(f"Title/desc generation failed: {e}")
        return {"title": "Untitled", "description": ""}


def _upload_workflow_impl(
    project_query: str,
    platform: str = "instagram",
    top_n: int = 2,
    caption_style: str = "",
    method: str = "auto",
    client_name: str = "",
) -> str:
    """
    Full upload workflow — CLIENT-AWARE with enforced priority chain:
    1. Search for project (return choices if duplicates)
    2. If client_name given, look up their upload_methods.json
    3. Auto-select method using MANDATORY priority order:
         Priority 1 — Metricool API Key  (api_key present)
         Priority 2 — Buffer API Key     (api_key present)
         Priority 3 — Platform API Key   (access_token present)
         Priority 4 — Login Credentials  (username+password via Playwright)
    4. Get top N clips
    5. Apply caption style (if specified)
    6. Generate title and description
    7. Report back with all info for Arc Agent handoff
    """
    from nex_agent.tools.storage_tools import _search_projects_impl, _get_clip_paths_impl

    # Step 1: Search
    matches = _search_projects_impl(project_query)
    if not matches:
        return json.dumps({
            "status": "no_matches",
            "message": f"No projects found matching '{project_query}'.",
        })

    if len(matches) > 1:
        return json.dumps({
            "status": "disambiguation_needed",
            "message": f"Found {len(matches)} projects matching '{project_query}'. Please specify which one:",
            "matches": matches,
        })

    match = matches[0]
    project_id = match.get("project_id", "")
    if not project_id:
        return json.dumps({
            "status": "error",
            "message": "Project found in storage but not in database. Cannot proceed.",
            "match": match,
        })

    # Step 2: Client lookup for upload method
    client_info = None
    resolved_method = method
    client_credentials = None

    if client_name:
        try:
            from nex_agent.tools.client_tools import _get_client_impl, _get_client_upload_method_impl
            client_result = json.loads(_get_client_impl(client_name))

            if client_result.get("status") == "found":
                client_info = client_result.get("client", {})
                client_id = client_info.get("client_id", "")

                # Auto-select method if set to "auto"
                if method == "auto" and client_id:
                    method_info = _get_client_upload_method_impl(client_id, platform)
                    if not method_info.get("error"):
                        resolved_method = method_info.get("method", "playwright")
                        if method_info.get("has_credentials"):
                            client_credentials = method_info.get("credentials", {})
                        else:
                            resolved_method = "playwright"  # Fallback

            elif client_result.get("status") == "multiple_matches":
                return json.dumps({
                    "status": "client_disambiguation_needed",
                    "message": f"Multiple clients match '{client_name}':",
                    "client_matches": client_result.get("matches", []),
                    "project": match,
                })
            else:
                return json.dumps({
                    "status": "client_not_found",
                    "message": f"No client found matching '{client_name}'. Create one with nex_create_client.",
                })
        except Exception as e:
            logger.warning(f"Client lookup failed: {e}")

    if resolved_method == "auto":
        resolved_method = "playwright"

    # Step 3: Get top clips
    clips = _get_clip_paths_impl(project_id, top_n, "portrait")
    if not clips:
        return json.dumps({"status": "error", "message": f"No clips found for project {project_id}."})

    # Step 4: Caption
    caption_info = None
    if caption_style:
        caption_info = {"style": caption_style, "note": "Apply captions before upload via caption API."}

    # Step 5: Generate title and description
    title_desc = _generate_title_description(project_id, clips, platform)

    # Step 6: Log the upload decision
    try:
        from nex_agent.activity_log import log_decision
        log_decision(
            decision=f"Upload {len(clips)} clips to {platform} via {resolved_method}",
            reasoning=f"Client: {client_name or 'none'}, Method: {resolved_method}, Project: {project_query}",
            alternatives=["metricool (P1)", "buffer (P2)", "api_key (P3)", "playwright (P4)"],
        )
    except Exception:
        pass

    return json.dumps({
        "status": "ready",
        "project": match,
        "clips": clips,
        "caption_style": caption_info,
        "generated_title": title_desc.get("title", ""),
        "generated_description": title_desc.get("description", ""),
        "platform": platform,
        "method": resolved_method,
        "client": client_info,
        "client_credentials": client_credentials,
        "instruction": (
            f"Ready to upload {len(clips)} clips to {platform} via {resolved_method}. "
            f"Hand this to Arc Agent with: arc_nexclip_upload_clips tool."
        ),
    }, indent=2)


def _upload_to_client_impl(
    project_query: str,
    client_name: str,
    platform: str = "instagram",
    top_n: int = 2,
    caption_style: str = "",
) -> str:
    """
    Simplified upload-to-client flow:
    'Upload top 2 clips from Test 1 to client Ved on Instagram'
    Auto-detects the best upload method for that client.
    """
    return _upload_workflow_impl(
        project_query=project_query,
        platform=platform,
        top_n=top_n,
        caption_style=caption_style,
        method="auto",
        client_name=client_name,
    )


# ══════════════════════════════════════════════════════════════
#  REGISTRATION
# ══════════════════════════════════════════════════════════════

def register(executor: "ToolExecutor") -> int:
    """Register upload workflow tools with the Nex Agent tool executor."""

    executor.register_tool(
        name="nex_upload_workflow",
        description=(
            "Full upload workflow: search project, look up client upload method, get top clips, "
            "apply captions, generate title/description, prepare Arc Agent handoff.\n"
            "If client_name is given, auto-selects method using MANDATORY priority chain:\n"
            "  Priority 1 → Metricool API Key (if api_key present)\n"
            "  Priority 2 → Buffer API Key (if api_key present)\n"
            "  Priority 3 → Platform API Key (if access_token present)\n"
            "  Priority 4 → Login Credentials / Playwright (fallback)\n"
            "Example: nex_upload_workflow(project_query='Test 1', client_name='Ved', "
            "platform='instagram', top_n=2, caption_style='opus_classic')"
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_query": {"type": "string", "description": "Project name to search for"},
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"],
                },
                "top_n": {"type": "integer", "description": "Number of top clips (default: 2)"},
                "caption_style": {"type": "string", "description": "Caption style ID. Available: opus_classic, ghost_karaoke, cinematic_lower, street_bold, neon_pulse, whisper_serif, punch_pop, matrix_code, sunset_warm, arctic_frost, electric_violet, retro_typewriter, comic_blast, minimal_mono, fire_gradient, ocean_depth, golden_luxury, glitch_cyber"},
                "method": {
                    "type": "string",
                    "enum": ["auto", "playwright", "metricool", "api_key"],
                    "description": "'auto' picks best for client. Default: auto",
                },
                "client_name": {"type": "string", "description": "Client name for method auto-selection"},
            },
            "required": ["project_query"],
        },
        handler=lambda project_query="", platform="instagram", top_n=2, caption_style="", method="auto", client_name="": (
            _upload_workflow_impl(project_query, platform, int(top_n), caption_style, method, client_name)
        ),
        category="upload",
    )

    executor.register_tool(
        name="nex_upload_to_client",
        description=(
            "Upload clips from a project to a specific client. Auto-detects upload method.\n"
            "Example: nex_upload_to_client(project_query='Test 1', client_name='Ved', "
            "platform='instagram', top_n=2)"
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_query": {"type": "string"},
                "client_name": {"type": "string"},
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"],
                },
                "top_n": {"type": "integer", "default": 2},
                "caption_style": {"type": "string", "default": ""},
            },
            "required": ["project_query", "client_name"],
        },
        handler=lambda project_query="", client_name="", platform="instagram", top_n=2, caption_style="": (
            _upload_to_client_impl(project_query, client_name, platform, int(top_n), caption_style)
        ),
        category="upload",
    )

    return 2

