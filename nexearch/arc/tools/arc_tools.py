"""
Arc Agent — Pipeline & Client Tools
======================================
Tools for controlling Nexearch pipelines, managing clients,
accessing data stores, and triggering evolution.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Pipeline Tools ─────────────────────────────────────────────

def pipeline_trigger(client_id: str, platform: str,
                      account_handle: str = "",
                      account_url: str = "",
                      dry_run: bool = True) -> Dict[str, Any]:
    """Trigger a full Nexearch pipeline for a client on a platform."""
    try:
        from nexearch.data.client_store import ClientDataStore
        from nexearch.tasks.pipeline import run_pipeline_task
        store = ClientDataStore(client_id)
        manifest = store.get_manifest() or {}
        creds = store.get_credentials(platform)
        resolved_account_url = account_url or creds.get("account_url", "")
        resolved_handle = account_handle or manifest.get("account_handle", client_id)

        if not resolved_account_url:
            return {
                "error": f"No account_url configured for {client_id} on {platform}",
                "client_id": client_id,
                "platform": platform,
            }

        task = run_pipeline_task.delay({
            "client_id": client_id,
            "platform": platform,
            "account_handle": resolved_handle,
            "account_url": resolved_account_url,
            "credentials": creds,
            "platform_credentials": {platform: creds} if creds else {},
            "dry_run": dry_run,
        })
        return {"task_id": task.id, "status": "queued", "client_id": client_id, "platform": platform}
    except Exception as e:
        return {"error": str(e), "hint": "Is Celery running?"}


def pipeline_status(task_id: str) -> Dict[str, Any]:
    """Check the status of a pipeline task."""
    try:
        from celery.result import AsyncResult
        from nexearch.tasks.pipeline import celery_app
        result = AsyncResult(task_id, app=celery_app)
        return {
            "task_id": task_id,
            "status": result.status,
            "result": str(result.result)[:500] if result.result else None,
        }
    except Exception as e:
        return {"error": str(e)}


def pipeline_scrape_only(client_id: str, platform: str,
                          method: str = "apify",
                          account_handle: str = "",
                          max_posts: int = 100) -> Dict[str, Any]:
    """Run only the scraping stage of the pipeline."""
    import asyncio

    try:
        from nexearch.agents.agent_scrape import DeepScrapeAgent
        from nexearch.agents.state import PipelineState
        from nexearch.data.client_store import ClientDataStore

        store = ClientDataStore(client_id)
        manifest = store.get_manifest() or {}
        creds = store.get_credentials(platform)
        state = PipelineState(
            client_id=client_id,
            platform=platform,
            account_handle=account_handle or manifest.get("account_handle", client_id),
            account_url=creds.get("account_url", ""),
            scraping_method=method,
            max_posts=max_posts,
            credentials=creds,
            platform_credentials={platform: creds} if creds else {},
        )
        agent = DeepScrapeAgent()
        result = asyncio.run(agent.run(state))
        return {
            "status": "complete",
            "posts_scraped": result.scrape_total,
            "errors": result.errors + result.scrape_errors,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Client Management Tools ───────────────────────────────────

def client_list() -> Dict[str, Any]:
    """List all Nexearch clients."""
    try:
        from nexearch.data.system_meta import SystemMeta
        meta = SystemMeta()
        return {"clients": meta.get_all_client_summaries()}
    except Exception as e:
        return {"error": str(e)}


def client_detail(client_id: str) -> Dict[str, Any]:
    """Get detailed info for a specific client."""
    try:
        from nexearch.data.client_store import ClientDataStore
        store = ClientDataStore(client_id)
        return store.get_client_summary()
    except Exception as e:
        return {"error": str(e)}


def client_dna(client_id: str, platform: str) -> Dict[str, Any]:
    """Get Account DNA for a client on a platform."""
    try:
        from nexearch.data.client_store import ClientDataStore
        store = ClientDataStore(client_id)
        return store.get_platform_dna(platform) or {"message": "No DNA yet"}
    except Exception as e:
        return {"error": str(e)}


def client_scrapes(client_id: str, platform: str,
                    limit: int = 20) -> Dict[str, Any]:
    """Get scraped posts for a client."""
    try:
        from nexearch.data.client_store import ClientDataStore
        store = ClientDataStore(client_id)
        return store.get_scrapes(platform, limit=limit)
    except Exception as e:
        return {"error": str(e)}


# ── Evolution Tools ────────────────────────────────────────────

def evolution_trigger(client_id: str, platform: str,
                       mode: str = "client") -> Dict[str, Any]:
    """Trigger an evolution cycle for a client."""
    try:
        from nexearch.agents.agent_evolve import EvolutionAgent
        from nexearch.agents.state import PipelineState
        state = PipelineState(client_id=client_id, platforms=[platform])
        agent = EvolutionAgent()
        result = agent.run(state)
        return {"status": "complete", "mode": mode, "result": str(result)[:500]}
    except Exception as e:
        return {"error": str(e)}


def evolution_history(client_id: str, platform: str = "all") -> Dict[str, Any]:
    """Get evolution history for a client."""
    try:
        from nexearch.data.client_store import ClientDataStore
        store = ClientDataStore(client_id)
        return store.get_evolution_history(platform)
    except Exception as e:
        return {"error": str(e)}


def universal_patterns(platform: str) -> Dict[str, Any]:
    """Get universal winning patterns for a platform."""
    try:
        from nexearch.data.universal_store import get_universal_store
        store = get_universal_store()
        return store.get_winning_patterns(platform)
    except Exception as e:
        return {"error": str(e)}


# ── Data Access Tools ──────────────────────────────────────────

def data_change_history(client_id: str,
                         change_type: str = "all") -> Dict[str, Any]:
    """Get change history for a client (system prompts, DNA updates, etc)."""
    try:
        from nexearch.data.change_tracker import ChangeTracker
        tracker = ChangeTracker(client_id)
        return {"changes": tracker.get_history(change_type=change_type)}
    except Exception as e:
        return {"error": str(e)}


def data_revert_change(client_id: str, change_id: str,
                        reason: str = "") -> Dict[str, Any]:
    """Revert a change and send negative feedback."""
    try:
        from nexearch.data.change_tracker import ChangeTracker
        tracker = ChangeTracker(client_id)
        return tracker.revert_change(change_id, reason=reason)
    except Exception as e:
        return {"error": str(e)}


def nexclip_enhancements(client_id: str) -> Dict[str, Any]:
    """Get NexClip enhancements for a client."""
    try:
        from nexearch.data.nexclip_client_store import NexClipClientStore
        store = NexClipClientStore(client_id)
        return store.generate_enhancement_report()
    except Exception as e:
        return {"error": str(e)}


# ── NexClip Bridge Tools ──────────────────────────────────────

def nexclip_get_clips(project_name: str, top_n: int = 2) -> Dict[str, Any]:
    """Get the top clips from a NexClip project's storage directory."""
    from pathlib import Path

    storage_root = Path(__file__).resolve().parents[3] / "backend" / "storage"
    project_dir = None

    # Search for project directory
    if storage_root.exists():
        for d in storage_root.iterdir():
            if d.is_dir() and project_name.lower() in d.name.lower():
                project_dir = d
                break

    if not project_dir:
        return {"error": f"Project '{project_name}' not found in storage"}

    # Find video files
    clips = []
    for vf in sorted(project_dir.glob("**/*.mp4")):
        clips.append({
            "path": str(vf),
            "name": vf.name,
            "size_mb": round(vf.stat().st_size / 1024 / 1024, 2),
        })

    if not clips:
        return {"error": f"No clips found in {project_dir}"}

    return {
        "project": project_name,
        "total_clips": len(clips),
        "top_clips": clips[:top_n],
    }


def _load_client_platform_credentials(client_id: str, platform: str) -> Dict[str, Any]:
    from nexearch.data.client_store import ClientDataStore

    store = ClientDataStore(client_id)
    return store.get_credentials(platform)


def _lookup_clip_metadata(clip_path: str) -> Dict[str, Any]:
    import sqlite3

    normalized_path = str(clip_path or "").strip()
    if not normalized_path:
        return {}

    repo_root = Path(__file__).resolve().parents[3]
    backend_root = repo_root / "backend"
    db_candidates = [
        backend_root / "nexclip.db",
        backend_root / "app" / "db" / "nexclip.db",
        backend_root / "scripts" / "nexclip.db",
    ]
    db_path = next((candidate for candidate in db_candidates if candidate.exists()), None)
    if not db_path:
        return {}

    project_folder = ""
    path_parts = Path(normalized_path).parts
    if "storage" in path_parts:
        storage_index = path_parts.index("storage")
        if len(path_parts) > storage_index + 1:
            project_folder = path_parts[storage_index + 1]

    stem = Path(normalized_path).stem
    normalized_stem = re.sub(r"_captioned(?:_opus_classic)?$", "", stem)
    clip_basename = f"{normalized_stem}.mp4"

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        conditions = [
            "c.file_path = ?",
            "c.file_path_landscape = ?",
            "c.captioned_video_url = ?",
            "c.captioned_video_url_landscape = ?",
        ]
        params: List[Any] = [normalized_path, normalized_path, normalized_path, normalized_path]

        if clip_basename:
            like_value = f"%/{clip_basename}"
            conditions.extend([
                "c.file_path LIKE ?",
                "c.file_path_landscape LIKE ?",
                "c.captioned_video_url LIKE ?",
                "c.captioned_video_url_landscape LIKE ?",
            ])
            params.extend([like_value, like_value, like_value, like_value])

        sql = """
            SELECT
                c.id AS clip_id,
                c.project_id AS project_id,
                p.title AS project_title,
                p.description AS project_description,
                c.title_suggestion AS title_suggestion,
                c.hook_text AS hook_text,
                c.reason AS reason,
                c.rank AS rank
            FROM clips c
            JOIN projects p ON p.id = c.project_id
            WHERE ({conditions})
        """.format(conditions=" OR ".join(conditions))

        if project_folder:
            project_token = project_folder.split("_")[-1]
            sql += """
                AND (
                    c.file_path LIKE ?
                    OR c.file_path_landscape LIKE ?
                    OR c.captioned_video_url LIKE ?
                    OR c.captioned_video_url_landscape LIKE ?
                    OR p.id LIKE ?
                )
            """
            prefix_value = f"{project_folder}/%"
            params.extend([prefix_value, prefix_value, prefix_value, prefix_value, f"{project_token}%"])

        sql += " ORDER BY c.rank ASC LIMIT 1"
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.close()

        if not row:
            return {}

        return {
            "clip_id": row["clip_id"],
            "project_id": row["project_id"],
            "project_title": row["project_title"] or "",
            "project_description": row["project_description"] or "",
            "title_suggestion": row["title_suggestion"] or "",
            "hook_text": row["hook_text"] or "",
            "reason": row["reason"] or "",
            "rank": row["rank"],
        }
    except Exception:
        return {}


def _fallback_clip_context(clip_path: str) -> Dict[str, Any]:
    path = Path(str(clip_path or ""))
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    readable_title = " ".join(part for part in stem.split() if part).strip()
    return {
        "title_suggestion": readable_title.title() if readable_title else "",
        "hook_text": readable_title[:120] if readable_title else "",
        "reason": f"Clip source: {path.name}" if path.name else "",
        "project_title": path.parent.name if path.parent else "",
    }


def _build_clip_context_text(client_id: str, platform: str, clip_path: str, metadata: Dict[str, Any]) -> str:
    context_lines = [
        f"Client ID: {client_id}",
        f"Target Platform: {platform}",
    ]
    if clip_path:
        context_lines.append(f"Clip Path: {clip_path}")
    if metadata.get("project_title"):
        context_lines.append(f"Project: {metadata['project_title']}")
    if metadata.get("project_description"):
        context_lines.append(f"Project Summary: {metadata['project_description']}")
    if metadata.get("title_suggestion"):
        context_lines.append(f"Suggested Angle: {metadata['title_suggestion']}")
    if metadata.get("hook_text"):
        context_lines.append(f"Hook: {metadata['hook_text']}")
    if metadata.get("reason"):
        context_lines.append(f"Why It Works: {metadata['reason']}")
    if metadata.get("rank") is not None:
        context_lines.append(f"Clip Rank: {metadata['rank']}")
    return "\n".join(line for line in context_lines if line.strip())


async def _generate_publish_metadata(
    *,
    client_id: str,
    platform: str,
    clip_path: str,
    title: str = "",
    description: str = "",
    caption: str = "",
) -> Dict[str, Any]:
    from nexearch.agents.agent_publish import PublisherAgent
    from nexearch.agents.state import PipelineState
    from nexearch.data.client_store import ClientDataStore

    store = ClientDataStore(client_id)
    manifest = store.get_manifest() or {}
    credentials = store.get_credentials(platform)
    raw_dna = store.get_platform_dna(platform) or {}
    account_dna = raw_dna.get("dna", raw_dna) if isinstance(raw_dna, dict) else {}

    clip_metadata = _lookup_clip_metadata(clip_path) or _fallback_clip_context(clip_path)
    source_title = str(clip_metadata.get("title_suggestion", "") or "").strip()
    source_hook = str(clip_metadata.get("hook_text", "") or "").strip()
    content_context = _build_clip_context_text(client_id, platform, clip_path, clip_metadata)
    source_truth_block = "\n".join(
        line for line in [
            f"Primary Title Suggestion: {source_title}" if source_title else "",
            f"Primary Hook: {source_hook}" if source_hook else "",
            (
                "Instruction: Write only from the clip's actual topic, hook, confession, insight, "
                "or named person/theme shown above."
            ),
            (
                "Instruction: Do not write generic creator, content strategy, brand building, "
                "workflow, or digital marketing copy unless the clip is specifically about that."
            ),
            "Instruction: Do not include hashtags inside the caption body.",
        ]
        if line
    )
    if source_truth_block:
        content_context = f"{content_context}\n\nSource Truth:\n{source_truth_block}"

    state = PipelineState(
        client_id=client_id,
        platform=platform,
        account_handle=manifest.get("account_handle", client_id),
        account_url=credentials.get("account_url", ""),
        account_dna=account_dna if isinstance(account_dna, dict) else {},
        clip_directive={
            "video_url": clip_path,
            "content_context": content_context,
            "writing_directives": {
                "title_directive": (
                    "Write a title that is specific to this exact clip. Use the provided title suggestion "
                    "and hook as the primary source material, lightly refined for the platform. "
                    "Do not write vague motivational or generic marketing hooks."
                ),
                "caption_directive": (
                    "Write a polished caption about this exact clip topic with a strong opening, clean flow, "
                    "and a CTA. The body must stay faithful to the provided hook/title suggestion and must "
                    "not introduce generic creator-economy, content-marketing, workflow, or brand-building language."
                ),
                "description_directive": (
                    "Write a platform-ready description that expands only on the clip's actual topic and hook."
                ),
                "hashtag_directive": (
                    "Return only 4-8 relevant hashtags as a comma-separated list, based on the exact clip topic, "
                    "person, industry, and hook. Avoid generic hashtags unless the clip is actually about them."
                ),
            },
        },
        credentials=credentials,
        platform_credentials={platform: credentials} if credentials else {},
    )

    writing = await PublisherAgent()._generate_writing(state)
    final_title = (title or "").strip() or writing.get("title", "") or source_title or source_hook
    final_caption = (caption or "").strip() or writing.get("caption", "")
    final_description = (description or "").strip() or writing.get("description", "")

    return {
        "title": final_title,
        "caption": final_caption,
        "description": final_description,
        "hashtags": writing.get("hashtags", []),
        "clip_metadata": clip_metadata,
        "content_context": content_context,
    }


def metricool_accessible_accounts(client_id: str, platform: str = "") -> Dict[str, Any]:
    """List the Metricool profiles reachable from a client's stored Metricool API key."""
    import asyncio

    from nexearch.data.client_store import ClientDataStore

    async def _do_list() -> Dict[str, Any]:
        from nexearch.tools.metricool import get_metricool_client

        store = ClientDataStore(client_id)
        requested_platforms = [platform] if platform else [
            candidate for candidate in ("instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads")
        ]

        token_map: Dict[str, str] = {}
        for candidate in requested_platforms:
            creds = store.get_credentials(candidate)
            metricool_api_key = str(creds.get("metricool_api_key", "") or "").strip()
            if metricool_api_key:
                token_map[candidate] = metricool_api_key

        if not token_map:
            return {
                "error": f"No Metricool API key stored for client '{client_id}'",
                "client_id": client_id,
                "platform": platform or "all",
            }

        responses = []
        seen_tokens = set()
        for source_platform, api_key in token_map.items():
            if api_key in seen_tokens:
                continue
            seen_tokens.add(api_key)
            client = get_metricool_client(access_token=api_key)
            profiles = await client.list_profiles()
            responses.append({
                "source_platform": source_platform,
                "profiles": [
                    {
                        "id": profile.get("id"),
                        "userId": profile.get("userId"),
                        "label": profile.get("label"),
                        "instagram": profile.get("instagram"),
                        "facebook": profile.get("facebook"),
                        "twitter": profile.get("twitter"),
                        "linkedin": profile.get("linkedin"),
                        "tiktok": profile.get("tiktok"),
                        "youtube": profile.get("youtube"),
                        "threads": profile.get("threads"),
                    }
                    for profile in profiles
                ],
            })

        return {
            "client_id": client_id,
            "platform": platform or "all",
            "accounts": responses,
        }

    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(lambda: asyncio.run(_do_list())).result()
    except RuntimeError:
        return asyncio.run(_do_list())


def nexclip_upload_clips(client_id: str, platform: str,
                           clips: str, method: str = "playwright",
                           caption_style: str = "",
                           title: str = "", description: str = "") -> Dict[str, Any]:
    """Upload clips to a client's social account using the specified method."""
    import asyncio

    try:
        clip_list = json.loads(clips) if isinstance(clips, str) else clips
    except json.JSONDecodeError:
        clip_list = [{"path": clips}]

    normalized_clips: List[Dict[str, Any]] = []
    for clip in clip_list or []:
        if isinstance(clip, dict):
            normalized_clips.append(clip)
        elif isinstance(clip, str):
            normalized_clips.append({"path": clip, "absolute_path": clip})
        elif clip is not None:
            path = str(clip)
            normalized_clips.append({"path": path, "absolute_path": path})
    clip_list = normalized_clips

    if method == "playwright":
        return _playwright_upload(platform, clip_list, title, description, caption_style, client_id=client_id)
    else:
        try:
            from nexearch.tools.publishers.publisher import create_publisher
            credentials = _load_client_platform_credentials(client_id, platform)
            publisher = create_publisher(method, platform, client_id=client_id, **credentials)
            results = []

            async def _do_publish():
                publish_results = []
                for clip in clip_list:
                    clip_path = clip.get("path") or clip.get("absolute_path", "")
                    generated = await _generate_publish_metadata(
                        client_id=client_id,
                        platform=platform,
                        clip_path=clip_path,
                        title=title,
                        description=description,
                        caption=caption_style,
                    )
                    max_retries = 3
                    for attempt in range(max_retries):
                        result = await publisher.publish(
                            video_url=clip_path,
                            caption=generated.get("caption", ""),
                            title=generated.get("title", ""),
                            description=generated.get("description", ""),
                            hashtags=generated.get("hashtags", []),
                            credentials=credentials,
                        )
                        if result.success:
                            break
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)

                    publish_results.append({
                        "success": result.success,
                        "error": result.error_message,
                        "title": generated.get("title", ""),
                        "caption": generated.get("caption", ""),
                        "description": generated.get("description", ""),
                        "hashtags": generated.get("hashtags", []),
                    })
                return publish_results

            # Safe async execution regardless of whether we're in an event loop
            try:
                loop = asyncio.get_running_loop()
                # Already inside an async context — run in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    results = pool.submit(lambda: asyncio.run(_do_publish())).result()
            except RuntimeError:
                # No running loop — safe to run directly
                results = asyncio.run(_do_publish())

            return {"uploaded": len([r for r in results if r["success"]]), "method": method, "results": results}
        except Exception as e:
            return {"error": str(e)}


def _resolve_playwright_credentials(client_id: str, platform: str) -> Dict[str, str]:
    """Prefer client-scoped upload credentials; fall back to env-based vault."""
    platform = platform.lower().strip()

    if client_id:
        try:
            from nexearch.data.client_store import ClientDataStore

            store = ClientDataStore(client_id)
            creds = store.get_credentials(platform)
            username = (creds.get("login_username") or "").strip()
            password = (creds.get("login_password") or "").strip()
            if username and password:
                return {
                    "username": username,
                    "password": password,
                    "platform": platform,
                }
        except Exception:
            pass

        upload_methods_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "clients"
            / client_id
            / "upload_methods.json"
        )
        if upload_methods_path.exists():
            try:
                methods = json.loads(upload_methods_path.read_text(encoding="utf-8"))
                config = methods.get(platform, {})
                creds = config.get("playwright", {})
                username = (creds.get("username") or creds.get("email") or "").strip()
                password = (creds.get("password") or "").strip()
                if username and password:
                    return {
                        "username": username,
                        "password": password,
                        "platform": platform,
                    }
            except Exception:
                pass

    from nexearch.tools.credential_vault import get_credentials
    return get_credentials(platform)


def _playwright_upload(
    platform: str,
    clip_list: List,
    title: str,
    description: str,
    caption: str,
    client_id: str = "",
) -> Dict[str, Any]:
    """Execute Playwright upload for clips."""
    import asyncio

    async def _do_upload():
        from nexearch.tools.publishers.playwright_publisher import PlaywrightPublisher
        credentials = _resolve_playwright_credentials(client_id, platform)
        publisher = PlaywrightPublisher(platform, headless=False)
        results = []
        for clip in clip_list:
            path = clip.get("path", clip.get("absolute_path", ""))
            result = await publisher.publish(
                video_path=path,
                caption=caption,
                title=title,
                description=description,
                credentials=credentials,
            )
            results.append(result)
        return results

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = pool.submit(lambda: asyncio.run(_do_upload())).result()
        else:
            results = loop.run_until_complete(_do_upload())

        return {
            "uploaded": len([r for r in results if r.get("success")]),
            "method": "playwright",
            "platform": platform,
            "results": results,
        }
    except Exception as e:
        return {"error": str(e), "method": "playwright"}


def arc_browse_storage(path: str = "") -> Dict[str, Any]:
    """Browse NexClip storage directory. Returns folders and files."""
    import os
    from pathlib import Path

    base = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))).resolve()
    storage_root = base / "backend" / "storage"

    if not storage_root.exists():
        return {"error": "Storage directory does not exist", "path": str(storage_root)}

    target = storage_root / path if path else storage_root
    if not target.exists():
        return {"error": f"Path not found: {target}"}

    entries = []
    for item in sorted(target.iterdir()):
        entry = {"name": item.name, "type": "dir" if item.is_dir() else "file"}
        if item.is_file():
            entry["size_mb"] = round(item.stat().st_size / 1e6, 2)
        elif item.is_dir():
            entry["children"] = len(list(item.iterdir()))
        entries.append(entry)

    return {"path": str(target), "entries": entries, "count": len(entries)}


def arc_check_credentials(platform: str) -> Dict[str, Any]:
    """Check if credentials are configured for a platform."""
    try:
        from nexearch.tools.credential_vault import (
            has_credentials, get_supported_platforms, get_all_configured_platforms,
        )
        if platform == "all":
            return {
                "supported": get_supported_platforms(),
                "configured": get_all_configured_platforms(),
            }
        return {
            "platform": platform,
            "has_credentials": has_credentials(platform),
            "supported": get_supported_platforms(),
        }
    except Exception as e:
        return {"error": str(e)}


def nex_agent_communicate(message: str, action: str = "chat") -> Dict[str, Any]:
    """Communicate with Nex Agent via the command bus."""
    try:
        import httpx
        response = httpx.post(
            "http://localhost:8001/api/chat",
            json={"message": message},
            timeout=30,
        )
        return {"response": response.json(), "from": "nex_agent"}
    except Exception as e:
        return {"error": str(e), "hint": "Is Nex Agent running on port 8001?"}


# ── Tool Registration ─────────────────────────────────────────

def register_all_arc_tools(executor) -> int:
    """Register all Arc Agent tools."""
    tools = [
        # Pipeline
        ("arc_pipeline_trigger", "Trigger a full Nexearch pipeline (scrape→analyze→score→evolve→bridge→publish).", "pipeline", pipeline_trigger,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"]}, "account_handle": {"type": "string", "default": ""}, "account_url": {"type": "string", "default": ""}, "dry_run": {"type": "boolean", "default": True}}, "required": ["client_id", "platform"]}),
        ("arc_pipeline_status", "Check the status of a running pipeline task.", "pipeline", pipeline_status,
         {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}),
        ("arc_pipeline_scrape_only", "Run only the scraping stage.", "pipeline", pipeline_scrape_only,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}, "method": {"type": "string", "default": "apify", "enum": ["apify", "platform_api", "crawlee_playwright", "buffer"]}, "account_handle": {"type": "string", "default": ""}, "max_posts": {"type": "integer", "default": 100}}, "required": ["client_id", "platform"]}),

        # Client Management
        ("arc_client_list", "List all Nexearch clients.", "client", client_list,
         {"type": "object", "properties": {}, "required": []}),
        ("arc_client_detail", "Get detailed info for a specific client.", "client", client_detail,
         {"type": "object", "properties": {"client_id": {"type": "string"}}, "required": ["client_id"]}),
        ("arc_client_dna", "Get Account DNA for a client on a platform.", "client", client_dna,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}}, "required": ["client_id", "platform"]}),
        ("arc_client_scrapes", "Get scraped posts for a client.", "client", client_scrapes,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["client_id", "platform"]}),

        # Evolution
        ("arc_evolution_trigger", "Trigger an evolution cycle.", "evolution", evolution_trigger,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}, "mode": {"type": "string", "default": "client", "enum": ["client", "universal"]}}, "required": ["client_id", "platform"]}),
        ("arc_evolution_history", "Get evolution history.", "evolution", evolution_history,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string", "default": "all"}}, "required": ["client_id"]}),
        ("arc_universal_patterns", "Get cross-client winning patterns for a platform.", "evolution", universal_patterns,
         {"type": "object", "properties": {"platform": {"type": "string"}}, "required": ["platform"]}),

        # Data / Change Tracking
        ("arc_change_history", "Get change history (system prompts, DNA updates, etc).", "data", data_change_history,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "change_type": {"type": "string", "default": "all"}}, "required": ["client_id"]}),
        ("arc_revert_change", "Revert a change and send negative feedback.", "data", data_revert_change,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "change_id": {"type": "string"}, "reason": {"type": "string", "default": ""}}, "required": ["client_id", "change_id"]}),
        ("arc_nexclip_enhancements", "Get NexClip enhancements for a client.", "data", nexclip_enhancements,
         {"type": "object", "properties": {"client_id": {"type": "string"}}, "required": ["client_id"]}),

        # NexClip Bridge
        ("arc_nexclip_get_clips", "Get clips from a NexClip project's storage.", "bridge", nexclip_get_clips,
         {"type": "object", "properties": {"project_name": {"type": "string"}, "top_n": {"type": "integer", "default": 2}}, "required": ["project_name"]}),
        ("arc_nexclip_upload_clips", "Upload clips to a client's social account.", "bridge", nexclip_upload_clips,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string"}, "clips": {"type": "string"}, "method": {"type": "string", "default": "playwright", "enum": ["metricool", "platform_api", "buffer", "playwright"]}, "caption_style": {"type": "string", "default": ""}, "title": {"type": "string", "default": ""}, "description": {"type": "string", "default": ""}}, "required": ["client_id", "platform", "clips"]}),

        ("arc_metricool_accessible_accounts", "List the Metricool profiles accessible from a client's stored Metricool API key.", "credentials", metricool_accessible_accounts,
         {"type": "object", "properties": {"client_id": {"type": "string"}, "platform": {"type": "string", "default": ""}}, "required": ["client_id"]}),

        # Nex Agent Communication
        ("arc_talk_to_nex_agent", "Send a message to Nex Agent and get a response. Arc↔Nex communication.", "communication", nex_agent_communicate,
         {"type": "object", "properties": {"message": {"type": "string"}, "action": {"type": "string", "default": "chat"}}, "required": ["message"]}),

        # Storage & Credentials
        ("arc_browse_storage", "Browse NexClip storage directory. Returns project folders and clip files.", "storage", arc_browse_storage,
         {"type": "object", "properties": {"path": {"type": "string", "default": "", "description": "Relative path within storage (empty for root)"}}, "required": []}),
        ("arc_check_credentials", "Check if platform credentials are configured. Use platform='all' to check all.", "credentials", arc_check_credentials,
         {"type": "object", "properties": {"platform": {"type": "string", "default": "all", "enum": ["all", "instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"]}}, "required": ["platform"]}),
    ]

    for name, desc, category, handler, params in tools:
        executor.register(name=name, description=desc, category=category,
                          handler=handler, parameters=params)

    return len(tools)
