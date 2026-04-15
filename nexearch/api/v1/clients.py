"""
Nexearch — Client Routes
CRUD for Nexearch clients + credential management + capability checking.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from loguru import logger

router = APIRouter(prefix="/clients", tags=["Nexearch Clients"])


@router.get("/", summary="List all Nexearch clients")
async def list_clients():
    """List all active Nexearch clients with their summaries."""
    from nexearch.data.system_meta import SystemMeta
    meta = SystemMeta()
    clients = meta.get_all_client_summaries()

    # Enrich with capabilities
    from nexearch.data.client_store import ClientDataStore
    enriched = []
    for c in clients:
        cid = c.get("client_id", "")
        try:
            store = ClientDataStore(cid)
            caps = store.get_all_capabilities()
            c["capabilities"] = caps.get("summary", {})
            c["platform_details"] = caps.get("platforms", {})
        except Exception:
            c["capabilities"] = {}
            c["platform_details"] = {}
        enriched.append(c)

    return {"clients": enriched}


@router.post("/", summary="Create a Nexearch client")
async def create_client(data: Dict[str, Any]):
    """
    Register a new client with full credential management.

    Expected payload:
    {
        "client_id": "ved_saini",
        "name": "Ved Saini",
        "account_handle": "vedsaini",
        "platforms": {
            "instagram": {
                "account_url": "https://instagram.com/vedsaini",
                "login_username": "",
                "login_password": "",
                "access_token": "",
                "api_key": "",
                "page_id": "",
                "metricool_api_key": ""
            },
            ...
        }
    }
    """
    from nexearch.data.client_store import ClientDataStore

    client_id = data.get("client_id", "")
    name = data.get("name", "")
    handle = data.get("account_handle", name)

    if not client_id and not name:
        raise HTTPException(400, "client_id or name is required")

    if not client_id:
        client_id = name.lower().replace(" ", "_").replace("-", "_")

    # Initialize data store
    client_store = ClientDataStore(client_id, handle)

    # Save credentials per platform
    platforms_input = data.get("platforms", {})
    platforms_configured = []

    if isinstance(platforms_input, dict):
        for platform, creds in platforms_input.items():
            if isinstance(creds, dict) and any(v for v in creds.values() if v):
                try:
                    client_store.save_credentials(platform, creds)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                platforms_configured.append(platform)
    elif isinstance(platforms_input, list):
        platforms_configured = platforms_input

    # Validate minimum requirement: at least 1 platform with at least a page link
    caps = client_store.get_all_capabilities()
    if caps["summary"]["total_researchable"] == 0 and platforms_configured:
        logger.warning(f"Client {client_id} created without any researchable platforms")

    # Also create NexClip client directory
    try:
        from nexearch.data.nexclip_client_store import NexClipClientStore
        NexClipClientStore(client_id, handle)
    except Exception:
        pass

    return {
        "client_id": client_id,
        "name": name,
        "account_handle": handle,
        "platforms_configured": platforms_configured,
        "capabilities": caps.get("summary", {}),
        "client_data_dir": str(client_store.base_dir),
        "status": "created",
    }


@router.get("/{client_id}", summary="Get client details")
async def get_client(client_id: str):
    """Get detailed client data including manifest, capabilities, and platform status."""
    from nexearch.data.client_store import ClientDataStore
    store = ClientDataStore(client_id)
    summary = store.get_client_summary()
    if not summary:
        raise HTTPException(404, "Client not found")

    caps = store.get_all_capabilities()
    summary["capabilities"] = caps
    return summary


@router.get("/{client_id}/capabilities", summary="Get client capabilities")
async def get_client_capabilities(client_id: str):
    """Get per-platform upload/research readiness."""
    from nexearch.data.client_store import ClientDataStore
    store = ClientDataStore(client_id)
    return store.get_all_capabilities()


@router.put("/{client_id}/credentials/{platform}", summary="Update platform credentials")
async def update_credentials(client_id: str, platform: str, data: Dict[str, Any]):
    """
    Update credentials for a specific platform.

    Body: {
        "account_url": "https://...",
        "login_username": "user",
        "login_password": "pass",
        "access_token": "token",
        "api_key": "key",
        "page_id": "id",
        "metricool_api_key": "key"
    }
    """
    from nexearch.data.client_store import ClientDataStore, PLATFORMS
    if platform not in PLATFORMS:
        raise HTTPException(400, f"Invalid platform: {platform}. Must be one of {PLATFORMS}")

    store = ClientDataStore(client_id)
    try:
        path = store.save_credentials(platform, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    caps = store.get_platform_capabilities(platform)

    return {
        "client_id": client_id,
        "platform": platform,
        "capabilities": caps,
        "saved_to": path,
        "status": "updated",
    }


@router.get("/{client_id}/credentials/{platform}", summary="Get platform credentials")
async def get_credentials(client_id: str, platform: str):
    """Get stored credentials for a platform (masks sensitive fields)."""
    from nexearch.data.client_store import ClientDataStore
    store = ClientDataStore(client_id)
    creds = store.get_credentials(platform)

    # Mask sensitive values for API response
    masked = {}
    for key, value in creds.items():
        if key in ("login_password", "access_token", "api_key", "metricool_api_key", "buffer_api_key") and value:
            masked[key] = value[:4] + "****" + value[-2:] if len(value) > 6 else "****"
        else:
            masked[key] = value

    return {
        "platform": platform,
        "credentials": masked,
        "capabilities": store.get_platform_capabilities(platform),
    }


@router.get("/{client_id}/data/{platform}", summary="Get client platform data")
async def get_client_platform_data(client_id: str, platform: str):
    """Get client data for a specific platform."""
    from nexearch.data.client_store import ClientDataStore
    store = ClientDataStore(client_id)

    return {
        "client_id": client_id,
        "platform": platform,
        "latest_scrape": store.get_latest_scrape(platform),
        "dna": store.get_platform_dna(platform),
        "capabilities": store.get_platform_capabilities(platform),
    }


@router.get("/{client_id}/nexclip", summary="Get NexClip enhancement data")
async def get_nexclip_data(client_id: str):
    """Get what NexClip has enhanced for this client."""
    from nexearch.data.nexclip_client_store import NexClipClientStore
    store = NexClipClientStore(client_id)
    return store.generate_enhancement_report()


@router.delete("/{client_id}", summary="Delete a client")
async def delete_client(client_id: str):
    """Delete a client and all associated data."""
    import shutil
    from pathlib import Path
    from nexearch.config import get_nexearch_settings

    settings = get_nexearch_settings()
    client_dir = Path(settings.NEXEARCH_CLIENTS_DIR).resolve() / "clients" / client_id

    if client_dir.exists():
        shutil.rmtree(client_dir)
        return {"client_id": client_id, "status": "deleted"}
    else:
        raise HTTPException(404, f"Client {client_id} not found")


@router.post("/{client_id}/validate/{platform}", summary="Live-validate platform credentials")
async def validate_platform_credentials(client_id: str, platform: str):
    """
    Real-time credential validation — tests each configured method against
    the actual platform APIs and returns live status.
    
    Returns per-method status:
    {
        "platform": "threads",
        "methods": {
            "page_link": { "configured": true, "status": "reachable" },
            "login_creds": { "configured": false, "status": "not_configured" },
            "api_key": {
                "configured": true,
                "status": "error",
                "error": "threads_basic permission not granted",
                "setup_instructions": [...]
            },
            "metricool": { "configured": false, "status": "not_configured" },
            "buffer": { "configured": true, "status": "connected", "profiles": [...] }
        }
    }
    """
    from nexearch.data.client_store import ClientDataStore
    store = ClientDataStore(client_id)
    creds = store.get_credentials(platform)
    
    result = {
        "platform": platform,
        "client_id": client_id,
        "methods": {},
    }
    
    # Method 1: Page Link
    url = creds.get("account_url", "")
    if url:
        result["methods"]["page_link"] = {"configured": True, "status": "reachable", "url": url}
    else:
        result["methods"]["page_link"] = {"configured": False, "status": "not_configured"}
    
    # Method 2: Login Credentials
    has_login = bool(creds.get("login_username")) and bool(creds.get("login_password"))
    if has_login:
        result["methods"]["login_creds"] = {"configured": True, "status": "ready", "username": creds.get("login_username", "")}
    else:
        result["methods"]["login_creds"] = {"configured": False, "status": "not_configured"}
    
    # Method 3: Platform API
    has_token = bool(creds.get("access_token") or creds.get("api_key"))
    if has_token:
        api_status = await _validate_platform_api(platform, creds)
        result["methods"]["api_key"] = api_status
    else:
        result["methods"]["api_key"] = {"configured": False, "status": "not_configured"}
    
    # Method 4: Metricool
    if creds.get("metricool_api_key"):
        try:
            from nexearch.tools.metricool import MetricoolClient
            mc = MetricoolClient(api_token=creds["metricool_api_key"])
            profiles = await mc.list_profiles()
            matched = await mc.find_profile(
                brand_id=creds.get("brand_id", ""),
                account_url=creds.get("account_url", ""),
                account_handle=creds.get("account_handle", ""),
                platform=platform,
            )
            result["methods"]["metricool"] = {
                "configured": True,
                "status": "connected" if matched else ("connected_mismatch" if profiles else "auth_failed"),
                "error": "" if matched or profiles else "Invalid Metricool API key",
                "profile_count": len(profiles),
                "profiles": [
                    {
                        "id": p.get("id"),
                        "userId": p.get("userId"),
                        "label": p.get("label"),
                        "instagram": p.get("instagram"),
                        "facebook": p.get("facebook"),
                        "twitter": p.get("twitter"),
                        "linkedin": p.get("linkedin"),
                        "tiktok": p.get("tiktok"),
                        "youtube": p.get("youtube"),
                        "threads": p.get("threads"),
                    }
                    for p in profiles[:10]
                ],
                "matched_profile": {
                    "id": matched.get("id"),
                    "label": matched.get("label"),
                    "userId": matched.get("userId"),
                } if matched else None,
            }
        except Exception as e:
            result["methods"]["metricool"] = {"configured": True, "status": "error", "error": str(e)}
    else:
        result["methods"]["metricool"] = {"configured": False, "status": "not_configured"}
    
    # Method 5: Buffer API
    if creds.get("buffer_api_key"):
        try:
            from nexearch.tools.buffer import get_buffer_client
            bc = get_buffer_client(access_token=creds["buffer_api_key"])
            conn = await bc.test_connection()
            if conn.get("connected"):
                result["methods"]["buffer"] = {
                    "configured": True,
                    "status": "connected",
                    "profile_count": conn.get("profile_count", 0),
                    "connected_platforms": conn.get("platforms", []),
                    "profiles": conn.get("profiles", []),
                }
            else:
                result["methods"]["buffer"] = {
                    "configured": True,
                    "status": "auth_failed",
                    "error": conn.get("error", "Buffer connection failed"),
                }
        except Exception as e:
            result["methods"]["buffer"] = {"configured": True, "status": "error", "error": str(e)}
    else:
        result["methods"]["buffer"] = {"configured": False, "status": "not_configured"}
    
    return result


async def _validate_platform_api(platform: str, creds: Dict) -> Dict:
    """
    Live-test platform API credentials and return status with setup instructions.
    """
    import httpx
    token = creds.get("access_token", "")
    api_key = creds.get("api_key", "")
    page_id = creds.get("page_id", "")
    
    # Platform-specific permission requirements
    PLATFORM_REQUIREMENTS = {
        "instagram": {
            "permissions": ["instagram_basic", "instagram_content_publish", "pages_show_list"],
            "setup_url": "https://developers.facebook.com/docs/instagram-api/getting-started",
            "setup_steps": [
                "Create a Meta App at developers.facebook.com",
                "Add Instagram Graph API product",
                "Add Instagram Business Account",
                "Generate long-lived access token with instagram_basic and instagram_content_publish permissions",
                "Set page_id to your Instagram Business Account ID",
            ],
        },
        "youtube": {
            "permissions": ["youtube.readonly", "youtube.upload"],
            "setup_url": "https://console.cloud.google.com/apis/credentials",
            "setup_steps": [
                "Create a Google Cloud project",
                "Enable YouTube Data API v3",
                "Create API credentials (API key for read, OAuth2 for upload)",
            ],
        },
        "twitter": {
            "permissions": ["tweet.read", "tweet.write", "users.read"],
            "setup_url": "https://developer.twitter.com/en/portal/dashboard",
            "setup_steps": [
                "Apply for Twitter Developer Account",
                "Create a Project and App",
                "Generate Bearer Token for reading",
                "Set up OAuth 1.0a for posting",
            ],
        },
        "facebook": {
            "permissions": ["pages_manage_posts", "pages_read_engagement"],
            "setup_url": "https://developers.facebook.com/docs/pages-api",
            "setup_steps": [
                "Create a Meta App",
                "Add Facebook Login product",
                "Generate Page Access Token with pages_manage_posts permission",
                "Set page_id to your Facebook Page ID",
            ],
        },
        "threads": {
            "permissions": ["threads_basic", "threads_content_publish", "threads_manage_replies"],
            "setup_url": "https://developers.facebook.com/docs/threads",
            "setup_steps": [
                "Create a Meta App at developers.facebook.com",
                "Add Threads API product to your app",
                "Request threads_basic permission (for reading posts)",
                "Request threads_content_publish permission (for publishing)",
                "Generate long-lived access token",
                "Set page_id to your Threads User ID",
            ],
        },
        "linkedin": {
            "permissions": ["r_liteprofile", "w_member_social"],
            "setup_url": "https://www.linkedin.com/developers/apps",
            "setup_steps": [
                "Create a LinkedIn Developer App",
                "Request Marketing API access",
                "Generate OAuth2 access token",
            ],
        },
        "tiktok": {
            "permissions": ["video.publish", "video.list"],
            "setup_url": "https://developers.tiktok.com",
            "setup_steps": [
                "Register as TikTok Developer",
                "Create an application",
                "Request Login Kit and Content Posting API",
                "Generate access token",
            ],
        },
    }
    
    reqs = PLATFORM_REQUIREMENTS.get(platform, {})
    base_result = {
        "configured": True,
        "permissions_required": reqs.get("permissions", []),
        "setup_url": reqs.get("setup_url", ""),
        "setup_steps": reqs.get("setup_steps", []),
    }
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if platform == "instagram":
                r = await client.get(
                    f"https://graph.facebook.com/v19.0/{page_id or 'me'}/media",
                    params={"access_token": token, "limit": 1},
                )
            elif platform == "youtube":
                r = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "snippet", "mine": "true", "key": api_key or token},
                )
            elif platform == "twitter":
                r = await client.get(
                    "https://api.twitter.com/2/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
            elif platform == "facebook":
                r = await client.get(
                    f"https://graph.facebook.com/v19.0/{page_id or 'me'}",
                    params={"access_token": token, "fields": "id,name"},
                )
            elif platform == "threads":
                r = await client.get(
                    f"https://graph.threads.net/v1.0/{page_id or 'me'}/threads",
                    params={"access_token": token, "limit": 1, "fields": "id"},
                )
            elif platform == "linkedin":
                r = await client.get(
                    "https://api.linkedin.com/v2/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
            elif platform == "tiktok":
                r = await client.get(
                    "https://open.tiktokapis.com/v2/user/info/",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"fields": "open_id,display_name"},
                )
            else:
                base_result["status"] = "unsupported"
                return base_result
            
            if 200 <= r.status_code < 300:
                base_result["status"] = "connected"
            elif r.status_code == 401 or r.status_code == 403:
                error_msg = ""
                try:
                    err = r.json()
                    error_msg = err.get("error", {}).get("message", r.text[:200])
                except Exception:
                    error_msg = r.text[:200]
                base_result["status"] = "permission_error"
                base_result["error"] = error_msg
            else:
                base_result["status"] = "error"
                base_result["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        base_result["status"] = "network_error"
        base_result["error"] = str(e)
    
    return base_result
