"""
Nex Agent — Client Management Tools
=========================================
Enterprise-grade client management system.
Each client has config, upload methods, and full history.

Client directory: NexClip/clients/{client_id}/
  - config.json           Clip generation preferences
  - upload_methods.json   Platform-specific upload method configs
  - history.json          Complete action history
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from nex_agent.tool_executor import ToolExecutor

from loguru import logger


# ── Constants ──────────────────────────────────────────────────

_CLIENTS_ROOT = Path(__file__).resolve().parent.parent.parent / "clients"
_NEXEARCH_CLIENTS = Path(__file__).resolve().parent.parent.parent / "nexearch" / "data" / "clients"

SUPPORTED_PLATFORMS = ["instagram", "tiktok", "youtube", "linkedin", "twitter", "facebook", "threads"]


def _ensure_client_dir(client_id: str) -> Path:
    """Create and return client directory."""
    d = _CLIENTS_ROOT / client_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_json(path: Path) -> Any:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)


def _add_history(client_id: str, action: str, details: Dict[str, Any]):
    """Append to client history."""
    d = _ensure_client_dir(client_id)
    history_path = d / "history.json"
    history = _load_json(history_path) or []
    history.append({
        "id": str(uuid.uuid4())[:12],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": action,
        "details": details,
    })
    _save_json(history_path, history)


# ══════════════════════════════════════════════════════════════
#  CLIENT CRUD
# ══════════════════════════════════════════════════════════════

def _create_client_impl(
    name: str,
    platforms: List[str] = None,
    upload_config: Dict[str, Any] = None,
    notes: str = "",
    account_url: str = "",
) -> str:
    """Create a new client.

    GUARD 0: account_url (page/account link) is mandatory.

    GUARD 1: Before creating, checks for existing clients with similar names.
    If a potential duplicate is found, returns status='duplicate_suspected'
    so the agent can show the user and ask for confirmation — NOT create blindly.

    GUARD 2: If no upload_config is provided — or all supplied method slots are empty
    credential dicts — returns status='method_required' so the agent must collect at
    least one real method + credentials first.
    """

    # ── Guard 0: Mandatory account_url ───────────────────────────────
    if not account_url or not account_url.strip():
        return json.dumps({
            "status": "account_url_required",
            "message": (
                "Cannot create client without a Page/Account Link. "
                "This is mandatory so Nexearch knows which social media account to analyse and upload to."
            ),
            "action_required": (
                "Ask the user: 'What is the URL of the social media page/account for this client? "
                "(e.g. https://www.instagram.com/clip_aura)'. "
                "Once provided, pass it as account_url to nex_create_client."
            ),
        }, indent=2)

    # ── Guard 1: Duplicate-name detection ────────────────────────────
    if _CLIENTS_ROOT.exists():
        query_norm = re.sub(r'[\s_\-]', '', name.lower().strip())
        similar: List[Dict[str, str]] = []
        for d in sorted(_CLIENTS_ROOT.iterdir()):
            if not d.is_dir():
                continue
            config_path = d / "config.json"
            existing = _load_json(config_path)
            if not existing:
                continue
            existing_name = existing.get("name", "")
            existing_norm = re.sub(r'[\s_\-]', '', existing_name.lower().strip())
            # Match if either name contains the other (normalised) or they are equal
            if (
                query_norm == existing_norm
                or query_norm in existing_norm
                or existing_norm in query_norm
            ):
                similar.append({
                    "client_id": existing.get("client_id", d.name),
                    "name": existing_name,
                    "platforms": existing.get("platforms", []),
                })

        if similar:
            return json.dumps({
                "status": "duplicate_suspected",
                "message": (
                    f"A client with a similar name already exists. "
                    f"Please confirm with the user whether they mean one of these "
                    f"existing clients, or explicitly want to create a brand-new separate client."
                ),
                "existing_clients": similar,
                "requested_name": name,
                "action_required": (
                    "Show these matches to the user and ASK: "
                    "'Did you mean [existing client name]? Or do you want to create a new, "
                    "separate client named [requested_name]?'"
                    " DO NOT call nex_create_client again until the user explicitly confirms."
                ),
            }, indent=2)

    # ── Guard 2: Mandatory method check ──────────────────────────────
    # Reject creation if no upload_config was supplied, or if every method slot
    # contains only empty credential dicts (no real credentials at all).
    # The agent MUST collect at least one method with real credentials first.

    def _has_any_real_cred(cfg: Dict[str, Any]) -> bool:
        """Return True if any credential field has a non-empty string value."""
        if not cfg:
            return False
        for v in cfg.values():
            if isinstance(v, dict):
                if any(str(vv).strip() for vv in v.values() if vv):
                    return True
            elif isinstance(v, str) and v.strip():
                return True
        return False

    has_real_method = bool(upload_config) and any(
        _has_any_real_cred(platform_cfg)
        for platform_cfg in (upload_config or {}).values()
        if isinstance(platform_cfg, dict)
    )

    if not has_real_method:
        return json.dumps({
            "status": "method_required",
            "message": (
                "Cannot create client without at least one upload/research method configured "
                "with real credentials. "
                "Ask the user which method they want to use before calling nex_create_client."
            ),
            "available_methods": [
                {"priority": 1, "method": "metricool", "credentials_needed": ["api_key"],          "description": "Metricool API — preferred. Handles research AND upload."},
                {"priority": 2, "method": "buffer",    "credentials_needed": ["api_key"],           "description": "Buffer API bridge (upload only)"},
                {"priority": 3, "method": "api_key",   "credentials_needed": ["access_token"],       "description": "Direct platform API (access_token)"},
                {"priority": 4, "method": "playwright", "credentials_needed": ["username", "password"],"description": "Browser automation / login credentials (fallback)"},
                {"priority": 5, "method": "page_link",  "credentials_needed": [],                     "description": "Page URL only — analysis only, cannot upload (account_url is still required)"},
            ],
            "action_required": (
                "Present these 5 options to the user and ask which method they want to use. "
                "Collect the required credentials, then pass them as upload_config to nex_create_client."
            ),
        }, indent=2)

    # ── All guards passed — proceed with creation ─────────────────
    client_id = re.sub(r'[^a-z0-9_]', '_', name.lower().strip()) + "_" + str(uuid.uuid4())[:6]
    d = _ensure_client_dir(client_id)

    config = {
        "client_id": client_id,
        "name": name,
        "account_url": account_url.strip(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platforms": platforms or SUPPORTED_PLATFORMS,
        "notes": notes,
        "access_methods": ["page_link", "login_credentials", "platform_api", "metricool", "buffer"],
        "clip_preferences": {
            "default_clip_count": 9,
            "default_duration_range": [15, 90],
            "preferred_caption_style": "",
            "preferred_aspect_ratio": "portrait",
        },
    }
    _save_json(d / "config.json", config)

    # Upload methods from upload_config (already validated non-empty above)
    _save_json(d / "upload_methods.json", upload_config)

    # Empty history
    _save_json(d / "history.json", [])

    _add_history(client_id, "client_created", {"name": name, "platforms": platforms})

    # Also create matching Nexearch client dir
    nx_dir = _NEXEARCH_CLIENTS / client_id
    nx_dir.mkdir(parents=True, exist_ok=True)
    _save_json(nx_dir / "meta.json", {
        "client_id": client_id, "name": name,
        "linked_nexclip_client": str(d),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    # Auto-trigger Nexearch Analytics Pipeline for all platforms
    import threading
    import requests
    def _trigger_auto_analysis(cid: str, hnd: str, plats: List[str]):
        time.sleep(2)  # Wait for dirs to settle
        for plat in plats:
            try:
                requests.post("http://localhost:8002/api/v1/nexearch/pipeline/run", json={
                    "client_id": cid,
                    "account_handle": hnd,
                    "platform": plat,
                    "skip_publish": True,
                    "enable_universal_evolution": True,
                }, timeout=5)
                logger.info(f"Auto-triggered Nexearch analysis for {cid} on {plat}")
            except Exception as e:
                logger.error(f"Failed to trigger auto-analysis for {cid} on {plat}: {e}")

    threading.Thread(
        target=_trigger_auto_analysis,
        args=(client_id, name, platforms or SUPPORTED_PLATFORMS),
        daemon=True,
    ).start()

    return json.dumps({
        "status": "created",
        "client_id": client_id,
        "name": name,
        "directory": str(d),
        "nexearch_directory": str(nx_dir),
        "message": "Client created with upload method configured. Auto-analysis pipeline triggered."
    }, indent=2)


def _get_client_impl(query: str) -> str:
    """Fuzzy search for a client by name or ID."""
    if not _CLIENTS_ROOT.exists():
        return json.dumps({"error": "No clients directory. Create a client first."})

    query_lower = query.lower().strip()
    matches = []

    for d in sorted(_CLIENTS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        config_path = d / "config.json"
        config = _load_json(config_path)
        if not config:
            continue

        name = config.get("name", d.name)
        cid = config.get("client_id", d.name)

        # Exact match
        if query_lower == name.lower() or query_lower == cid.lower():
            matches.insert(0, config)
            continue

        # Fuzzy match
        if query_lower in name.lower() or query_lower in cid.lower():
            matches.append(config)

    if not matches:
        return json.dumps({"status": "not_found", "message": f"No client matching '{query}'"})

    if len(matches) == 1:
        m = matches[0]
        cid = m["client_id"]
        methods = _load_json(_CLIENTS_ROOT / cid / "upload_methods.json") or {}
        history = _load_json(_CLIENTS_ROOT / cid / "history.json") or []
        return json.dumps({
            "status": "found",
            "client": m,
            "upload_methods": methods,
            "history_count": len(history),
            "last_actions": history[-5:] if history else [],
        }, indent=2)

    return json.dumps({
        "status": "multiple_matches",
        "message": f"Found {len(matches)} clients matching '{query}':",
        "matches": [{"client_id": m["client_id"], "name": m["name"]} for m in matches],
    }, indent=2)


def _update_client_upload_method_impl(
    client_id: str,
    platform: str,
    method: str,
    credentials: Dict[str, str] = None,
) -> str:
    """Update a client's upload method for a platform."""
    d = _CLIENTS_ROOT / client_id
    if not d.exists():
        return json.dumps({"error": f"Client '{client_id}' not found."})

    methods_path = d / "upload_methods.json"
    methods = _load_json(methods_path) or {}

    if platform not in methods:
        methods[platform] = {
            "method": "none",  # "metricool" | "api_key" | "playwright" | "buffer" | "none"
            "metricool": {"brand_id": "", "api_key": ""},
            "api_key": {"access_token": "", "access_secret": ""},
            "playwright": {"username": "", "password": ""},
        }

    methods[platform]["method"] = method

    if credentials:
        if method == "metricool":
            methods[platform].setdefault("metricool", {}).update(credentials)
        elif method == "api_key":
            methods[platform].setdefault("api_key", {}).update(credentials)
        elif method == "playwright":
            methods[platform].setdefault("playwright", {}).update(credentials)
        elif method == "buffer":
            methods[platform].setdefault("buffer", {}).update(credentials)

    _save_json(methods_path, methods)
    _add_history(client_id, "upload_method_updated", {
        "platform": platform, "method": method,
        "credentials_provided": list(credentials.keys()) if credentials else [],
    })

    return json.dumps({
        "status": "updated",
        "client_id": client_id,
        "platform": platform,
        "method": method,
    })


def _list_clients_impl() -> str:
    """List all NexClip clients."""
    if not _CLIENTS_ROOT.exists():
        return json.dumps({"clients": [], "message": "No clients created yet."})

    clients = []
    for d in sorted(_CLIENTS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        config = _load_json(d / "config.json")
        if config:
            methods = _load_json(d / "upload_methods.json") or {}
            configured_methods = {}
            for plat, m in methods.items():
                meth = m.get("method", "none")
                if meth != "none":
                    configured_methods[plat] = meth

            clients.append({
                "client_id": config.get("client_id", d.name),
                "name": config.get("name", d.name),
                "platforms": config.get("platforms", []),
                "configured_upload_methods": configured_methods,
                "created_at": config.get("created_at", ""),
            })

    return json.dumps({"clients": clients, "total": len(clients)}, indent=2)


def _get_client_upload_method_impl(client_id: str, platform: str) -> Dict[str, Any]:
    """Get the upload method and credentials for a client on a specific platform.

    PRIORITY ORDER (non-negotiable):
      1. Metricool API Key  (brand_id + api_key)
      2. Buffer API Key     (api_key)
      3. Platform API Key   (access_token)
      4. Login Credentials  (username + password via Playwright)

    Even if the stored 'method' field says something else, we ALWAYS auto-waterfall
    through this priority chain and pick the first method that has real credentials.
    This ensures that if a Metricool key exists for a client, it is ALWAYS used first.
    """
    d = _CLIENTS_ROOT / client_id
    if not d.exists():
        return {"error": f"Client '{client_id}' not found"}

    methods = _load_json(d / "upload_methods.json") or {}
    plat_config = methods.get(platform)
    if not plat_config:
        return {"error": f"No upload config for {platform}", "method": "none"}

    def _has_creds(creds: dict) -> bool:
        """Return True if any credential field has a non-empty value."""
        return bool(creds and any(str(v).strip() for v in creds.values() if v))

    # ── Priority Chain ────────────────────────────────────────────
    # 1. Metricool — requires brand_id AND api_key
    metricool_creds = plat_config.get("metricool", {})
    if _has_creds(metricool_creds) and metricool_creds.get("api_key", "").strip():
        logger.info(
            f"[Priority] Client '{client_id}' › platform '{platform}' "
            f"→ Using METRICOOL (highest priority, API key present)"
        )
        return {
            "client_id": client_id,
            "platform": platform,
            "method": "metricool",
            "credentials": metricool_creds,
            "has_credentials": True,
            "priority_resolved": True,
            "priority_level": 1,
        }

    # 2. Buffer
    buffer_creds = plat_config.get("buffer", {})
    if _has_creds(buffer_creds) and buffer_creds.get("api_key", "").strip():
        logger.info(
            f"[Priority] Client '{client_id}' › platform '{platform}' "
            f"→ Using BUFFER (priority 2, Metricool not configured)"
        )
        return {
            "client_id": client_id,
            "platform": platform,
            "method": "buffer",
            "credentials": buffer_creds,
            "has_credentials": True,
            "priority_resolved": True,
            "priority_level": 2,
        }

    # 3. Platform API Key
    api_key_creds = plat_config.get("api_key", {})
    if _has_creds(api_key_creds) and api_key_creds.get("access_token", "").strip():
        logger.info(
            f"[Priority] Client '{client_id}' › platform '{platform}' "
            f"→ Using PLATFORM API KEY (priority 3)"
        )
        return {
            "client_id": client_id,
            "platform": platform,
            "method": "api_key",
            "credentials": api_key_creds,
            "has_credentials": True,
            "priority_resolved": True,
            "priority_level": 3,
        }

    # 4. Login Credentials (Playwright)
    playwright_creds = plat_config.get("playwright", {})
    if _has_creds(playwright_creds) and playwright_creds.get("username", "").strip():
        logger.info(
            f"[Priority] Client '{client_id}' › platform '{platform}' "
            f"→ Using PLAYWRIGHT / Login Credentials (priority 4, fallback)"
        )
        return {
            "client_id": client_id,
            "platform": platform,
            "method": "playwright",
            "credentials": playwright_creds,
            "has_credentials": True,
            "priority_resolved": True,
            "priority_level": 4,
        }

    # ── No credentials found in any slot — report clearly ────────
    saved_method = plat_config.get("method", "none")
    logger.warning(
        f"[Priority] Client '{client_id}' › platform '{platform}' "
        f"→ No usable credentials found in any priority slot. Saved method was '{saved_method}'."
    )
    return {
        "client_id": client_id,
        "platform": platform,
        "method": "none",
        "credentials": {},
        "has_credentials": False,
        "priority_resolved": False,
        "priority_level": None,
        "message": (
            f"No credentials configured for '{platform}'. "
            "Please add Metricool API key, Buffer API key, Platform API token, or Login credentials."
        ),
    }


def _get_client_history_impl(client_id: str, limit: int = 50) -> str:
    """Get a client's full action history."""
    d = _CLIENTS_ROOT / client_id
    if not d.exists():
        return json.dumps({"error": f"Client '{client_id}' not found"})

    history = _load_json(d / "history.json") or []
    return json.dumps({
        "client_id": client_id,
        "total_actions": len(history),
        "recent_actions": history[-limit:],
    }, indent=2)


# ══════════════════════════════════════════════════════════════
#  REGISTRATION
# ══════════════════════════════════════════════════════════════

def register(executor: "ToolExecutor") -> int:
    """Register client management tools."""

    executor.register_tool(
        name="nex_create_client",
        description=(
            "Create a new NexClip client. "
            "This creates both NexClip and Nexearch client directories.\n"
            "Supported platforms: instagram, tiktok, youtube, linkedin, twitter, facebook, threads (7 total).\n\n"

            "━━━ TWO MANDATORY INPUTS — COLLECT BOTH BEFORE CALLING nex_create_client ━━━\n"
            "  1. account_url  — The social media page/account URL (e.g. https://instagram.com/clip_aura).\n"
            "                    This is NON-NEGOTIABLE. No client is created without it.\n"
            "  2. upload_config — At least one method with real credentials (see below).\n\n"

            "━━━ MANDATORY PRE-CHECK — DO THIS BEFORE CALLING nex_create_client ━━━\n"
            "STEP 1 — Search first: ALWAYS call nex_get_client(query='<name>') BEFORE creating.\n"
            "STEP 2 — If ANY similar client name is found, show the user the existing client and ASK:\n"
            "   'Did you mean [existing client]? Or do you want to create a brand-new client?'\n"
            "STEP 3 — ONLY call nex_create_client if the user explicitly confirms they want a NEW client.\n"
            "         If they say it's the existing client, use that client — DO NOT create.\n\n"

            "━━━ MANDATORY METHOD ━━━\n"
            "You MUST collect at least one upload/research method from the user before calling this tool.\n"
            "Creating a client without a method is BLOCKED by the system (returns method_required).\n"
            "Present these 5 options and ask the user which one they want to use:\n"
            "  1 (Highest) Metricool API Key  — credentials: api_key  [handles Research AND Upload]\n"
            "  2           Buffer API Key     — credentials: api_key  [upload only]\n"
            "  3           Platform API Key   — credentials: access_token\n"
            "  4 (Fallback) Login Credentials — credentials: username + password\n"
            "  5 (Analysis only) Page Link    — no extra credentials (account_url still required)\n\n"

            "━━━ PASSING upload_config ━━━\n"
            "Build upload_config as a dict keyed by platform with the chosen method and credentials.\n"
            "Example for Metricool on Instagram:\n"
            "  upload_config = {\n"
            "    'instagram': {\n"
            "      'method': 'metricool',\n"
            "      'metricool': {'api_key': '<key>'},\n"
            "      'buffer': {'api_key': ''},\n"
            "      'api_key': {'access_token': ''},\n"
            "      'playwright': {'username': '', 'password': ''}\n"
            "    }\n"
            "  }\n"
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Client name"},
                "account_url": {
                    "type": "string",
                    "description": "MANDATORY: Full URL of the social media page/account (e.g. https://instagram.com/clip_aura)",
                },
                "platforms": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Platforms this client uses (default: all 7)",
                },
                "upload_config": {
                    "type": "object",
                    "description": "MANDATORY: Upload config keyed by platform. Must include at least one method with real credentials.",
                },
                "notes": {"type": "string", "description": "Optional notes about the client"},
            },
            "required": ["name", "account_url", "upload_config"],
        },
        handler=lambda name="", account_url="", platforms=None, upload_config=None, notes="": (
            _create_client_impl(name, platforms, upload_config, notes, account_url)
        ),
        category="client",
    )

    executor.register_tool(
        name="nex_get_client",
        description=(
            "Find a client by name or ID (fuzzy search). Returns config, upload methods, and recent history.\n"
            "Example: nex_get_client(query='Ved') or nex_get_client(query='darshik')"
        ),
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Client name or ID to search for"}},
            "required": ["query"],
        },
        handler=lambda query="": _get_client_impl(query),
        category="client",
    )

    executor.register_tool(
        name="nex_update_client_upload",
        description=(
            "Update a client's upload method for a platform. "
            "5 Methods available:\n"
            "  'metricool' — credentials={brand_id, api_key}\n"
            "  'api_key'   — credentials={access_token, access_secret}\n"
            "  'playwright'— credentials={username, password}\n"
            "  'buffer'    — credentials={api_key}\n"
            "  'page_link' — no credentials needed (set account_url in Nexearch)\n"
            "Supported platforms: instagram, tiktok, youtube, linkedin, twitter, facebook, threads.\n"
            "Example: nex_update_client_upload(client_id='ved_abc123', platform='threads', "
            "method='buffer', credentials={'api_key': 'buf_xxx'})"
        ),
        parameters={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "platform": {"type": "string", "enum": SUPPORTED_PLATFORMS},
                "method": {"type": "string", "enum": ["metricool", "api_key", "playwright", "buffer", "page_link"]},
                "credentials": {"type": "object", "description": "Credentials dict (varies by method)"},
            },
            "required": ["client_id", "platform", "method"],
        },
        handler=lambda client_id="", platform="", method="", credentials=None: (
            _update_client_upload_method_impl(client_id, platform, method, credentials)
        ),
        category="client",
    )

    executor.register_tool(
        name="nex_list_clients",
        description="List all NexClip clients with their configured upload methods.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=lambda: _list_clients_impl(),
        category="client",
    )

    executor.register_tool(
        name="nex_get_client_history",
        description="Get a client's complete action history (uploads, config changes, etc).",
        parameters={
            "type": "object",
            "properties": {
                "client_id": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["client_id"],
        },
        handler=lambda client_id="", limit=50: _get_client_history_impl(client_id, int(limit)),
        category="client",
    )

    return 5
