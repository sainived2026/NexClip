"""
Nex Agent — Video Processing Tools
========================================
Tools for triggering video processing, clip generation,
and project status monitoring directly from chat.

Examples:
  "Generate 9 clips from https://youtu.be/xyz, name it Raj Test 1"
  "Check processing status for Raj Test 1"
"""

from __future__ import annotations

import json
import os
import re
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

from loguru import logger

# ── Active processing monitors ──────────────────────────────────
_active_monitors: Dict[str, threading.Thread] = {}


def _current_request_context() -> Dict[str, str]:
    """Read the active Nex chat context if this tool was invoked from a conversation."""
    try:
        from nex_agent.request_context import get_request_context

        context = get_request_context()
        user_id = (context.get("user_id") or "").strip()
        conversation_id = (context.get("conversation_id") or "").strip()
        if user_id and conversation_id:
            return {"user_id": user_id, "conversation_id": conversation_id}
    except Exception:
        pass
    return {}


def _get_backend_url() -> str:
    return os.environ.get("NEXCLIP_BACKEND_URL", "http://localhost:8000")


def _monitor_processing(
    project_id: str, project_name: str,
    poll_interval: int = 15,
    pipeline_context: Dict = None,
):
    """Background thread that polls project status and chains post-processing on completion."""
    import httpx

    backend = _get_backend_url()
    token = _get_auth_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    max_wait = 3600  # 1 hour max
    elapsed = 0
    request_context = (pipeline_context or {}).get("request_context", {})

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        try:
            resp = httpx.get(
                f"{backend}/api/projects/{project_id}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"Monitor poll got {resp.status_code} for {project_id[:8]}")
                continue

            data = resp.json()
            raw_status = data.get("status", "")
            status = raw_status.lower() if isinstance(raw_status, str) else str(raw_status).lower()
            clips = data.get("clips", [])
            logger.debug(f"Monitor: {project_name} status='{raw_status}' clips={len(clips)}")

            if status in ("completed", "complete", "done"):
                # Processing complete — push notification
                _push_notification(
                    project_id=project_id,
                    project_name=project_name,
                    clip_count=len(clips),
                    status="completed",
                    target_context=request_context,
                )

                # Chain post-processing if pipeline context exists
                if pipeline_context:
                    try:
                        _chain_post_processing(
                            project_id=project_id,
                            project_name=project_name,
                            clip_count=len(clips),
                            context=pipeline_context,
                        )
                    except Exception as chain_err:
                        logger.error(f"Pipeline chain failed: {chain_err}")
                        _send_proactive_chat(
                            f"❌ **Pipeline chain error** for '{project_name}': {chain_err}",
                            target_context=request_context,
                        )
                break
            elif status in ("error", "failed"):
                _push_notification(
                    project_id=project_id,
                    project_name=project_name,
                    clip_count=0,
                    status="failed",
                    error=data.get("error_message", data.get("status_message", "")),
                    target_context=request_context,
                )
                break
        except Exception as e:
            logger.warning(f"Monitor poll error for {project_name}: {e}")
            continue

    # Cleanup
    _active_monitors.pop(project_id, None)
    logger.info(f"Monitor ended for '{project_name}' (project_id={project_id[:8]})")


def _publish_proactive_message(
    message: str,
    target_context: Dict[str, str] | None = None,
    notification: Dict[str, Any] | None = None,
) -> str:
    """Persist and dispatch a proactive assistant message to the active Nex chat."""
    from nex_agent.core import get_nex_agent
    from nex_agent.websocket import ws_manager

    payload = {
        "type": "proactive_message",
        "message_id": f"pipe_{int(time.time())}_{os.urandom(4).hex()}",
        "content": message,
        "role": "assistant",
    }
    if notification:
        payload["notification"] = notification

    context = target_context or {}
    user_id = (context.get("user_id") or "").strip()
    conversation_id = (context.get("conversation_id") or "").strip()

    try:
        agent = get_nex_agent()
        sm = getattr(agent, "streaming_manager", None)
        if sm and user_id and conversation_id:
            sm.save_assistant_message(
                payload["message_id"],
                conversation_id,
                user_id,
                message,
                rich_type="notification" if notification else "",
                rich_data=notification,
            )
    except Exception as persist_err:
        logger.warning(f"Failed to persist proactive message: {persist_err}")

    if user_id:
        try:
            if ws_manager.dispatch_to_user(user_id, payload):
                return payload["message_id"]
        except Exception as ws_err:
            logger.warning(f"Thread-safe proactive dispatch failed: {ws_err}")

    delivered = False
    for connected_user_id in list(ws_manager.connections.keys()):
        try:
            delivered = ws_manager.dispatch_to_user(connected_user_id, payload) or delivered
        except Exception as ws_err:
            logger.warning(f"Broadcast proactive dispatch failed for {connected_user_id}: {ws_err}")

    if not delivered:
        try:
            agent = get_nex_agent()
            agent.broadcaster.broadcast(payload)
        except Exception as queue_err:
            logger.warning(f"Failed to queue proactive message: {queue_err}")

    return payload["message_id"]


def _push_notification(
    project_id: str,
    project_name: str,
    clip_count: int,
    status: str,
    error: str = "",
    target_context: Dict[str, str] | None = None,
):
    """Push a notification to the Nex Agent UI and active chat conversation."""
    try:
        notif_dir = Path(__file__).resolve().parent.parent / "nex_agent_memory" / "notifications"
        notif_dir.mkdir(parents=True, exist_ok=True)

        if status == "completed":
            chat_message = (
                f"✅ **Processing Complete** — Project **'{project_name}'** is ready!\n\n"
                f"My crop engine has successfully generated **{clip_count} clips**. "
                f"You can now preview and edit them in the dashboard.\n\n"
                f"Head over to the project to review your clips."
            )
        else:
            chat_message = (
                f"❌ **Processing Failed** — Project **'{project_name}'** encountered an error.\n\n"
                f"Error: {error}\n\n"
                f"Please check the pipeline logs or try re-processing the video."
            )

        notification = {
            "id": f"notif_{int(time.time())}_{project_id[:8]}",
            "type": "processing_complete" if status == "completed" else "processing_failed",
            "project_id": project_id,
            "project_name": project_name,
            "clip_count": clip_count,
            "status": status,
            "error": error,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "read": False,
            "message": chat_message,
        }

        notif_path = notif_dir / f"{notification['id']}.json"
        with open(notif_path, "w", encoding="utf-8") as f:
            json.dump(notification, f, indent=2)

        logger.info(f"Notification pushed: {notification['message'][:80]}...")
        _publish_proactive_message(chat_message, target_context=target_context, notification=notification)

    except Exception as e:
        logger.warning(f"Failed to push notification: {e}")


def _send_proactive_chat(message: str, target_context: Dict[str, str] | None = None):
    """Send a proactive chat message to the active conversation when possible."""
    try:
        _publish_proactive_message(message, target_context=target_context)
    except Exception as e:
        logger.warning(f"Proactive chat send failed: {e}")


def _chain_post_processing(
    project_id: str,
    project_name: str,
    clip_count: int,
    context: Dict,
):
    """
    Multi-step pipeline chain that runs AFTER clips are generated:
    1. Apply caption style to top N clips
    2. Create/find client and save credentials
    3. Hand off to Arc Agent for upload
    4. Report per-clip upload status back to user
    """
    from nex_agent.agent_bus import get_agent_bus
    bus = get_agent_bus()

    caption_style = context.get("caption_style", "")
    client_name = context.get("client_name", "")
    platform = context.get("platform", "instagram")
    upload_method = context.get("upload_method", "playwright")
    credentials = context.get("credentials", {})
    top_n = context.get("top_n", 6)
    request_context = context.get("request_context", {})

    bus.pipeline_event("nex_agent", f"Pipeline chain started for '{project_name}'",
                       project_id=project_id, steps=["captions", "client", "upload"])

    # ── Step 1: Get top clips ──────────────────────────────────
    bus.pipeline_event("nex_agent", f"Fetching top {top_n} clips from '{project_name}'")
    try:
        clips_json = _get_project_clips_impl(project_id=project_id)
        clips_data = json.loads(clips_json)
        all_clips = clips_data.get("clips", [])
        top_clips = all_clips[:top_n]

        if not top_clips:
            _send_proactive_chat(
                f"⚠️ No clips found for '{project_name}'. Pipeline chain stopped.",
                target_context=request_context,
            )
            return

        bus.tool_result("nex_agent", "nex_get_project_clips",
                        f"{len(top_clips)} clips selected (top by viral score)")
    except Exception as e:
        _send_proactive_chat(
            f"❌ Failed to fetch clips for '{project_name}': {e}",
            target_context=request_context,
        )
        return

    # ── Step 2: Apply captions ─────────────────────────────────
    if caption_style:
        _send_proactive_chat(
            f"✅ **Clips generated!** Now applying caption style **'{caption_style}'** "
            f"to the top {len(top_clips)} clips from '{project_name}'...",
            target_context=request_context,
        )
        bus.pipeline_event("nex_agent", f"Applying caption style '{caption_style}' to {len(top_clips)} clips")

        captioned_count = 0
        for i, clip in enumerate(top_clips, 1):
            try:
                from nex_agent.tools.upload_tools import _apply_caption_to_clip
                result = _apply_caption_to_clip(clip.get("file_path", ""), caption_style, project_id)
                if not result.get("error"):
                    captioned_count += 1
                    bus.tool_result("nex_agent", "apply_caption",
                                    f"Clip {i}/{len(top_clips)} captioned")
                else:
                    bus.log("nex_agent", "system", "error",
                            f"Caption failed for clip {i}: {result.get('error')}")
            except Exception as e:
                logger.warning(f"Caption failed for clip {i}: {e}")

        if captioned_count > 0:
            _send_proactive_chat(
                f"🎬 Captions applied to **{captioned_count}/{len(top_clips)}** clips. "
                f"Now setting up upload...",
                target_context=request_context,
            )
        else:
            _send_proactive_chat(
                f"⚠️ Caption application had issues. Proceeding with original clips...",
                target_context=request_context,
            )
    else:
        _send_proactive_chat(
            f"✅ **{clip_count} clips generated** for '{project_name}'! "
            f"Now setting up upload to **{platform}**...",
            target_context=request_context,
        )

    # ── Step 3: Client setup ───────────────────────────────────
    client_id_resolved = ""
    if client_name:
        bus.pipeline_event("nex_agent", f"Setting up client '{client_name}' for {platform}")
        try:
            from nex_agent.tools.client_tools import _create_client_impl, _get_client_impl
            import json as _json

            # Check if client exists
            existing = _json.loads(_get_client_impl(client_name))
            if existing.get("status") == "found":
                client_id_resolved = existing.get("client", {}).get("client_id", "")
            else:
                # Create client
                create_result = _json.loads(_create_client_impl(client_name))
                client_id_resolved = create_result.get("client_id", "")
                bus.nex_to_arc(f"Created new client '{client_name}' ({client_id_resolved})", msg_type="status_update")
                _send_proactive_chat(
                    f"📋 Created client **'{client_name}'**",
                    target_context=request_context,
                )

            # Save credentials if provided and we have a client_id
            if credentials and client_id_resolved:
                from nex_agent.tools.client_tools import _update_client_upload_method_impl
                cred_result = _update_client_upload_method_impl(
                    client_id_resolved, platform, upload_method, credentials
                )
                bus.nex_to_arc(
                    f"Saved {platform} credentials for '{client_name}'",
                    msg_type="status_update",
                )
        except Exception as e:
            logger.warning(f"Client setup failed: {e}")
            bus.log("nex_agent", "system", "error", f"Client setup failed: {e}")

    # ── Step 4: Hand off to Arc Agent for upload ───────────────
    bus.nex_to_arc(
        f"Requesting upload of {len(top_clips)} clips from '{project_name}' to {platform} "
        f"via {upload_method} for client '{client_name}'",
        msg_type="task_delegation",
    )
    _send_proactive_chat(
        f"🤖 Handing off to **Arc Agent** for upload to **{platform}**...\n"
        f"Arc Agent will upload {len(top_clips)} clips one by one.",
        target_context=request_context,
    )

    # Attempt upload via deterministic Arc bridge tool execution
    try:
        from nexearch.bridge import get_arc_bridge

        # Resolve absolute clip paths for Arc Agent
        backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
        abs_clip_paths = []
        for c in top_clips:
            rel_path = c.get('file_path', '')
            if rel_path:
                abs_path = str((backend_dir / "storage" / rel_path).resolve())
                if os.path.exists(abs_path):
                    abs_clip_paths.append(abs_path)
                else:
                    abs_clip_paths.append(rel_path)  # fallback to relative

        bridge = get_arc_bridge()
        arc_response = bridge.execute_tool(
            "arc_nexclip_upload_clips",
            {
                "client_id": client_id_resolved,
                "platform": platform,
                "clips": json.dumps(abs_clip_paths),
                "method": upload_method,
                "caption_style": caption_style,
            },
        )
        upload_result = arc_response.get("result", {}) if isinstance(arc_response, dict) else {}
        bus.arc_to_nex(
            f"Upload task acknowledged: {str(arc_response)[:200]}",
            msg_type="status_update",
        )

        # Report completion
        if upload_result and not upload_result.get("error"):
            uploaded = upload_result.get("uploaded", 0)
            _send_proactive_chat(
                f"Arc upload finished for '{client_name or client_id_resolved or 'client'}'. "
                f"Uploaded {uploaded}/{len(top_clips)} clips to {platform} using {upload_method}.",
                target_context=request_context,
            )
        else:
            _send_proactive_chat(
                f"Arc Agent could not complete the upload task. "
                f"Reason: {upload_result.get('error', 'No upload result returned from Arc Agent.')}",
                target_context=request_context,
            )
    except Exception as e:
        logger.error(f"Arc Agent upload handoff failed: {e}")
        bus.log("nex_agent", "system", "error", f"Upload handoff failed: {e}")
        _send_proactive_chat(
            f"❌ **Upload handoff failed**: {e}\n"
            f"The clips are ready in the dashboard. You can upload them manually "
            f"or ask me to retry.",
            target_context=request_context,
        )

    bus.pipeline_event("nex_agent", f"Pipeline chain completed for '{project_name}'")


def _get_auth_token() -> str:
    """Get a stored admin auth token for backend API calls."""
    import httpx
    # Try to read cached token
    token_path = Path(__file__).resolve().parent.parent / "nex_agent_memory" / ".backend_token"
    if token_path.exists():
        token = token_path.read_text().strip()
        if token:
            # Verify it's still valid
            try:
                resp = httpx.get(
                    f"{_get_backend_url()}/api/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                )
                if resp.status_code == 200:
                    return token
            except Exception:
                pass

    # Login as admin to get a token
    try:
        resp = httpx.post(
            f"{_get_backend_url()}/api/auth/login",
            json={"email": "admin@nexclip.local", "password": "admin"},
            timeout=10,
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            if token:
                token_path.parent.mkdir(parents=True, exist_ok=True)
                token_path.write_text(token)
                return token
    except Exception:
        pass

    return ""


def _process_video_impl(
    url: str,
    project_name: str = "",
    clip_count: int = 9,
    max_duration: int = 90,
    min_duration: int = 15,
    client_id: str = "",
) -> str:
    """Trigger video processing pipeline via the NexClip backend API."""
    import httpx

    backend = _get_backend_url()
    token = _get_auth_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        # Create project via URL endpoint
        create_payload = {
            "url": url,
            "title": project_name or f"Project_{time.strftime('%Y%m%d_%H%M%S')}",
            "clip_count": clip_count,
        }
        if client_id:
            create_payload["client_id"] = client_id

        resp = httpx.post(
            f"{backend}/api/projects/url",
            json=create_payload,
            headers=headers,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            return json.dumps({
                "status": "error",
                "message": f"Failed to create project: {resp.status_code} — {resp.text[:500]}",
            })

        project_data = resp.json()
        project_id = project_data.get("id", project_data.get("project_id", ""))

        # Processing is auto-enqueued by the backend on project creation
        # Start background monitor to track completion and push notifications
        if project_id:
            # Build pipeline context from extra args if available
            pipeline_ctx = None
            if hasattr(_process_video_impl, '_pipeline_context'):
                pipeline_ctx = _process_video_impl._pipeline_context
                _process_video_impl._pipeline_context = None
            request_context = _current_request_context()
            if request_context:
                if pipeline_ctx is None:
                    pipeline_ctx = {}
                pipeline_ctx.setdefault("request_context", request_context)

            monitor = threading.Thread(
                target=_monitor_processing,
                args=(project_id, project_name or create_payload["title"]),
                kwargs={"pipeline_context": pipeline_ctx},
                daemon=True,
            )
            monitor.start()
            _active_monitors[project_id] = monitor
            logger.info(f"Started background monitor for '{project_name}' ({project_id[:8]})")

            # Log to AgentBus
            try:
                from nex_agent.agent_bus import get_agent_bus
                bus = get_agent_bus()
                bus.pipeline_event("nex_agent",
                    f"Video processing started for '{project_name}' ({clip_count} clips)",
                    project_id=project_id, url=url)
                if pipeline_ctx:
                    steps = []
                    if pipeline_ctx.get("caption_style"): steps.append("captions")
                    if pipeline_ctx.get("client_name"): steps.append("client_setup")
                    if pipeline_ctx.get("platform"): steps.append("upload")
                    bus.pipeline_event("nex_agent",
                        f"Pipeline chain queued: {' → '.join(steps)}",
                        project_id=project_id)
            except Exception:
                pass

        return json.dumps({
            "status": "processing",
            "project_id": project_id,
            "project_name": project_name or create_payload['title'],
            "url": url,
            "clip_count": clip_count,
            "message": (
                f"Video processing started for **'{project_name or create_payload['title']}'**. "
                f"Generating {clip_count} clips from the provided video. "
                f"You'll be notified once processing completes."
            ),
        }, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": f"Failed to trigger processing: {e}"})


def _check_processing_impl(project_name: str = "", project_id: str = "") -> str:
    """Check the status of a video processing job."""
    import httpx

    backend = _get_backend_url()
    token = _get_auth_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # If we have a project_id, use it directly
    if project_id:
        try:
            resp = httpx.get(f"{backend}/api/projects/{project_id}", headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return json.dumps({
                    "status": data.get("status", "unknown"),
                    "progress": data.get("progress", 0),
                    "status_message": data.get("status_message", ""),
                    "project_id": project_id,
                    "title": data.get("title", ""),
                    "clip_count": len(data.get("clips", [])),
                }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Check failed: {e}"})

    # If we have project_name, search
    if project_name:
        try:
            resp = httpx.get(f"{backend}/api/projects/", headers=headers, timeout=15)
            if resp.status_code == 200:
                projects = resp.json()
                if isinstance(projects, dict):
                    projects = projects.get("projects", projects.get("items", []))

                matches = []
                for p in projects:
                    title = p.get("title", "")
                    if project_name.lower() in title.lower():
                        matches.append({
                            "project_id": p.get("id", ""),
                            "title": title,
                            "status": p.get("status", "unknown"),
                            "progress": p.get("progress", 0),
                            "status_message": p.get("status_message", ""),
                            "clip_count": len(p.get("clips", [])),
                            "created_at": p.get("created_at", ""),
                        })

                if not matches:
                    return json.dumps({"status": "not_found", "message": f"No project matching '{project_name}'"})

                if len(matches) == 1:
                    return json.dumps(matches[0], indent=2)

                return json.dumps({
                    "status": "multiple_matches",
                    "matches": matches,
                }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Search failed: {e}"})

    return json.dumps({"error": "Provide either project_name or project_id"})


def _get_project_clips_impl(project_name: str = "", project_id: str = "") -> str:
    """Get clips for a project with metadata."""
    import httpx

    backend = _get_backend_url()
    token = _get_auth_token()
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        if not project_id and project_name:
            # Search for project first
            resp = httpx.get(f"{backend}/api/projects/", headers=headers, timeout=15)
            if resp.status_code == 200:
                projects = resp.json()
                if isinstance(projects, dict):
                    projects = projects.get("projects", projects.get("items", []))
                for p in projects:
                    if project_name.lower() in p.get("title", "").lower():
                        project_id = p.get("id", "")
                        break

        if not project_id:
            return json.dumps({"error": f"Project '{project_name}' not found"})

        resp = httpx.get(f"{backend}/api/projects/{project_id}", headers=headers, timeout=15)
        if resp.status_code != 200:
            return json.dumps({"error": f"Failed to get project: {resp.status_code}"})

        data = resp.json()
        clips = data.get("clips", [])

        clip_info = []
        for c in clips:
            clip_info.append({
                "id": c.get("id", ""),
                "title": c.get("title_suggestion", ""),
                "viral_score": c.get("viral_score", 0),
                "start_time": c.get("start_time", 0),
                "end_time": c.get("end_time", 0),
                "duration": round((c.get("end_time", 0) or 0) - (c.get("start_time", 0) or 0), 1),
                "file_path": c.get("file_path", ""),
                "portrait_url": c.get("portrait_video_url", ""),
                "landscape_url": c.get("landscape_video_url", ""),
                "captioned": bool(c.get("captioned_portrait_url") or c.get("captioned_landscape_url")),
                "captioned_portrait": c.get("captioned_portrait_url", ""),
                "captioned_landscape": c.get("captioned_landscape_url", ""),
            })

        # Sort by viral score
        clip_info.sort(key=lambda x: x.get("viral_score", 0), reverse=True)

        return json.dumps({
            "project_id": project_id,
            "title": data.get("title", ""),
            "total_clips": len(clip_info),
            "clips": clip_info,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Failed to get clips: {e}"})


# ══════════════════════════════════════════════════════════════
#  REGISTRATION
# ══════════════════════════════════════════════════════════════

def register(executor: "ToolExecutor") -> int:
    """Register video processing tools."""

    executor.register_tool(
        name="nex_process_video",
        description=(
            "Trigger video processing: download a video and generate clips from it. "
            "Works with YouTube URLs, direct video URLs, or any URL NexClip supports.\n"
            "When this tool succeeds, tell the user that processing has started, "
            "how many clips are being generated, and that they'll be notified on completion. "
            "Be natural and conversational — do NOT use a canned template response.\n"
            "Example: nex_process_video(url='https://youtu.be/xyz', "
            "project_name='Raj Test 1', clip_count=9)"
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Video URL (YouTube, direct, etc)"},
                "project_name": {"type": "string", "description": "Name for the project"},
                "clip_count": {"type": "integer", "description": "Number of clips to generate (default: 9)"},
                "max_duration": {"type": "integer", "description": "Max clip duration in seconds (default: 90)"},
                "min_duration": {"type": "integer", "description": "Min clip duration in seconds (default: 15)"},
                "client_id": {"type": "string", "description": "UUID of the client to use for DNA injection (e.g., 'Ved Saini' -> fetch ID first via nexearch tools or just pass client name if supported, else leave empty)"},
            },
            "required": ["url"],
        },
        handler=lambda url="", project_name="", clip_count=9, max_duration=90, min_duration=15, client_id="": (
            _process_video_impl(url, project_name, int(clip_count), int(max_duration), int(min_duration), client_id)
        ),
        category="video",
    )

    executor.register_tool(
        name="nex_check_processing",
        description=(
            "Check the status of a video processing job by name or ID. "
            "The user can ask you to check status naturally — they do NOT need to type any code. "
            "When the user says 'check status of Test 1' or 'how is Test 1 doing', call this tool.\n"
            "Report the status, progress percentage, and clip count from the tool output.\n"
            "Example: nex_check_processing(project_name='Raj Test 1')"
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project name to search for"},
                "project_id": {"type": "string", "description": "Project ID (if known)"},
            },
            "required": [],
        },
        handler=lambda project_name="", project_id="": (
            _check_processing_impl(project_name, project_id)
        ),
        category="video",
    )

    executor.register_tool(
        name="nex_get_project_clips",
        description=(
            "Get all clips for a project with metadata (viral score, duration, file paths, "
            "caption status). Clips are sorted by viral score (best first).\n"
            "Example: nex_get_project_clips(project_name='Raj Test 1')"
        ),
        parameters={
            "type": "object",
            "properties": {
                "project_name": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": [],
        },
        handler=lambda project_name="", project_id="": (
            _get_project_clips_impl(project_name, project_id)
        ),
        category="video",
    )

    def _process_pipeline_handler(
        url="", project_name="", clip_count=9,
        caption_style="", client_name="", platform="instagram",
        upload_method="playwright", top_n=6,
        credentials_json="",
        max_duration=90, min_duration=15,
        client_id="",
    ):
        """Full pipeline: generate clips → apply captions → set up client → upload via Arc Agent."""
        import json as _json

        # Parse credentials
        creds = {}
        if credentials_json:
            try:
                creds = _json.loads(credentials_json)
            except Exception:
                pass

        # Set pipeline context on _process_video_impl so the monitor thread picks it up
        pipeline_ctx = {
            "caption_style": caption_style,
            "client_name": client_name,
            "platform": platform,
            "upload_method": upload_method,
            "top_n": int(top_n),
            "credentials": creds,
        }
        _process_video_impl._pipeline_context = pipeline_ctx

        # Call the standard video processing (which starts the monitor thread)
        result = _process_video_impl(url, project_name, int(clip_count), int(max_duration), int(min_duration), client_id)

        # Enhance the response to include pipeline info
        try:
            result_data = _json.loads(result)
            steps = []
            if caption_style: steps.append(f"apply caption style '{caption_style}'")
            if client_name: steps.append(f"set up client '{client_name}'")
            steps.append(f"upload to {platform} via {upload_method}")

            result_data["pipeline"] = {
                "steps": steps,
                "caption_style": caption_style,
                "client_name": client_name,
                "platform": platform,
                "upload_method": upload_method,
                "top_n": int(top_n),
            }
            result_data["message"] = (
                f"Processing started for **'{project_name or 'Untitled'}'** — generating {clip_count} clips. "
                f"Pipeline steps queued: {', '.join(steps)}. "
                f"You'll receive updates as each step completes."
            )
            return _json.dumps(result_data, indent=2)
        except Exception:
            return result

    executor.register_tool(
        name="nex_process_pipeline",
        description=(
            "FULL AUTONOMOUS PIPELINE: Generate clips + apply captions + create client + upload to social media.\n"
            "This is the MOST POWERFUL tool — use it when the user wants to do MULTIPLE things in one command.\n"
            "Example: 'generate 9 clips from this video, apply opus_classic captions to the top 6, "
            "and upload to Instagram for client Ved_Saini-Clip_Aura'\n\n"
            "When this tool succeeds, briefly tell the user what pipeline steps are queued "
            "and that you will send proactive updates. Be natural and conversational — "
            "do NOT repeat the same canned template every time.\n\n"
            "AVAILABLE CAPTION STYLES (pick one): "
            "opus_classic, ghost_karaoke, cinematic_lower, street_bold, neon_pulse, "
            "whisper_serif, punch_pop, matrix_code, sunset_warm, arctic_frost, "
            "electric_violet, retro_typewriter, comic_blast, minimal_mono, "
            "fire_gradient, ocean_depth, golden_luxury, glitch_cyber\n\n"
            "Example call: nex_process_pipeline(url='https://youtu.be/xyz', project_name='Test 3', "
            "clip_count=9, caption_style='opus_classic', client_name='Ved_Saini-Clip_Aura', "
            "platform='instagram', upload_method='playwright', top_n=6)"
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Video URL (YouTube, direct, etc)"},
                "project_name": {"type": "string", "description": "Name for the project"},
                "clip_count": {"type": "integer", "description": "Number of clips to generate (default: 9)"},
                "caption_style": {"type": "string", "description": "Caption style ID. Available: opus_classic, ghost_karaoke, cinematic_lower, street_bold, neon_pulse, whisper_serif, punch_pop, matrix_code, sunset_warm, arctic_frost, electric_violet, retro_typewriter, comic_blast, minimal_mono, fire_gradient, ocean_depth, golden_luxury, glitch_cyber"},
                "client_name": {"type": "string", "description": "Client name for upload (e.g. 'Ved_Saini-Clip_Aura')"},
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook"],
                    "description": "Target platform (default: instagram)",
                },
                "upload_method": {
                    "type": "string",
                    "enum": ["auto", "playwright", "metricool", "platform_api"],
                    "description": "Upload method (default: playwright)",
                },
                "top_n": {"type": "integer", "description": "Number of top clips to caption+upload (default: 6)"},
                "credentials_json": {"type": "string", "description": "JSON string of platform credentials (e.g. '{\"username\": \"x\", \"password\": \"y\"}')"},
                "max_duration": {"type": "integer", "description": "Max clip duration in seconds (default: 90)"},
                "min_duration": {"type": "integer", "description": "Min clip duration in seconds (default: 15)"},
            },
            "required": ["url"],
        },
        handler=_process_pipeline_handler,
        category="video",
    )

    return 4
