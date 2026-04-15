"""
Nexearch — Buffer API Client
Enterprise-grade async client for the Buffer REST API (Beta).
Supports: profile listing, post creation, connection testing, and account URL extraction.
Buffer is used for both UPLOADING (via post creation API) and RESEARCH 
(by extracting connected account URLs to feed into Crawlee/Playwright scrapers).
"""

import httpx
import asyncio
import json
from typing import Optional, Dict, Any, List
from loguru import logger

from nexearch.config import get_nexearch_settings


class BufferError(Exception):
    """Custom exception for Buffer API errors."""
    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Buffer Error ({status_code}): {message}")


# Map Buffer service names to Nexearch platform names
BUFFER_TO_NEXEARCH_PLATFORM = {
    "instagram": "instagram",
    "tiktok": "tiktok",
    "youtube": "youtube",
    "linkedin": "linkedin",
    "twitter": "twitter",
    "facebook": "facebook",
    "threads": "threads",
    "x": "twitter",
    "googlebusiness": None,
    "pinterest": None,
    "mastodon": None,
    "bluesky": None,
    "startpage": None,
    "shopify": None,
}


class BufferClient:
    """
    Async Buffer API client with:
    - Retry logic (3 attempts, exponential backoff)
    - Profile listing (to extract connected account URLs)
    - Post creation (text + media + video)
    - Connection testing
    """

    def __init__(self, access_token: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_nexearch_settings()
        self._token = access_token or settings.BUFFER_ACCESS_TOKEN
        self._base_url = base_url or settings.BUFFER_BASE_URL
        self._max_retries = 3
        self._base_delay = 1.0

        if not self._token:
            logger.warning("BufferClient: No access token configured. Operations will fail.")

    @property
    def is_configured(self) -> bool:
        return bool(self._token)

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an API request with retry and error handling."""
        url = f"{self._base_url}{endpoint}"
        if params is None:
            params = {}
        params["access_token"] = self._token
        last_error = None

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                        data=data,
                    )

                    # Rate limit handling
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", "60"))
                        logger.warning(f"Buffer rate limited. Waiting {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue

                    # Success
                    if 200 <= response.status_code < 300:
                        if response.text:
                            return response.json()
                        return {"status": "ok", "status_code": response.status_code}

                    # Client/server error
                    raise BufferError(
                        message=response.text[:500],
                        status_code=response.status_code,
                        response_body=response.text,
                    )

            except BufferError:
                raise
            except Exception as e:
                last_error = e
                delay = self._base_delay * (2 ** attempt)
                logger.warning(
                    f"Buffer request failed (attempt {attempt + 1}/{self._max_retries}): {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        raise BufferError(
            message=f"All {self._max_retries} retries failed. Last error: {last_error}",
            status_code=0,
        )

    # ── Profile Management ──────────────────────────────────

    async def list_profiles(self) -> List[Dict[str, Any]]:
        """
        List all connected social profiles in this Buffer account.
        Each profile contains: id, service, service_username, service_id, avatar_url, etc.
        
        We use this to:
        1. Extract connected account URLs for Crawlee research
        2. Get profile IDs for publishing
        """
        return await self._request("GET", "/profiles.json")

    async def get_profile(self, profile_id: str) -> Dict[str, Any]:
        """Get a specific profile by ID."""
        return await self._request("GET", f"/profiles/{profile_id}.json")

    async def get_profiles_for_platform(self, platform: str) -> List[Dict[str, Any]]:
        """Get Buffer profiles for a specific Nexearch platform."""
        all_profiles = await self.list_profiles()
        if not isinstance(all_profiles, list):
            return []
        
        results = []
        for profile in all_profiles:
            service = profile.get("service", "").lower()
            mapped = BUFFER_TO_NEXEARCH_PLATFORM.get(service)
            if mapped == platform:
                results.append(profile)
        return results

    async def extract_account_urls(self) -> Dict[str, str]:
        """
        Extract account URLs from all connected Buffer profiles.
        Returns: { platform: account_url } for each connected platform.
        
        This is the KEY function for research: Buffer gives us the connected
        accounts, and we feed those URLs into Crawlee/Playwright for scraping.
        """
        all_profiles = await self.list_profiles()
        if not isinstance(all_profiles, list):
            return {}

        urls = {}
        for profile in all_profiles:
            service = profile.get("service", "").lower()
            platform = BUFFER_TO_NEXEARCH_PLATFORM.get(service)
            if not platform:
                continue

            # Extract the best URL for this profile
            service_username = profile.get("service_username", "")
            formatted_username = profile.get("formatted_username", "")
            
            url = ""
            if platform == "instagram":
                url = f"https://instagram.com/{service_username}" if service_username else ""
            elif platform == "tiktok":
                url = f"https://tiktok.com/@{service_username}" if service_username else ""
            elif platform == "youtube":
                url = f"https://youtube.com/{formatted_username or service_username}" if (formatted_username or service_username) else ""
            elif platform == "linkedin":
                url = f"https://linkedin.com/in/{service_username}" if service_username else ""
            elif platform == "twitter":
                url = f"https://x.com/{service_username}" if service_username else ""
            elif platform == "facebook":
                url = f"https://facebook.com/{service_username}" if service_username else ""
            elif platform == "threads":
                url = f"https://threads.net/@{service_username}" if service_username else ""
            
            if url and platform not in urls:
                urls[platform] = url

        return urls

    # ── Publishing ────────────────────────────────────────────

    async def create_post(
        self,
        profile_ids: List[str],
        text: str = "",
        media: Optional[Dict] = None,
        scheduled_at: Optional[str] = None,
        now: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a post via Buffer.
        
        Args:
            profile_ids: List of Buffer profile IDs to post to
            text: Post text/caption
            media: Optional media dict with keys: link, photo, thumbnail, video, title, description
            scheduled_at: ISO datetime string for scheduling
            now: If True, share immediately
        """
        post_data: Dict[str, Any] = {
            "profile_ids[]": profile_ids,
            "text": text,
        }

        if media:
            if media.get("photo"):
                post_data["media[photo]"] = media["photo"]
            if media.get("thumbnail"):
                post_data["media[thumbnail]"] = media["thumbnail"]
            if media.get("video"):
                post_data["media[video]"] = media["video"]
            if media.get("title"):
                post_data["media[title]"] = media["title"]
            if media.get("description"):
                post_data["media[description]"] = media["description"]
            if media.get("link"):
                post_data["media[link]"] = media["link"]

        if scheduled_at:
            post_data["scheduled_at"] = scheduled_at
        elif now:
            post_data["now"] = "true"
        else:
            post_data["now"] = "true"

        return await self._request("POST", "/updates/create.json", data=post_data)

    # ── Connection Testing ────────────────────────────────────

    async def test_connection(self) -> Dict[str, Any]:
        """
        Test if the Buffer access token is valid.
        Returns connection status with profile count and connected platforms.
        """
        try:
            profiles = await self.list_profiles()
            if isinstance(profiles, list):
                connected_platforms = set()
                for p in profiles:
                    service = p.get("service", "").lower()
                    mapped = BUFFER_TO_NEXEARCH_PLATFORM.get(service)
                    if mapped:
                        connected_platforms.add(mapped)
                
                return {
                    "connected": True,
                    "profile_count": len(profiles),
                    "platforms": sorted(connected_platforms),
                    "profiles": [
                        {
                            "id": p.get("id"),
                            "service": p.get("service"),
                            "username": p.get("service_username"),
                            "avatar": p.get("avatar_https"),
                        }
                        for p in profiles
                    ],
                }
            return {"connected": False, "error": "Invalid response from Buffer API"}
        except Exception as e:
            logger.error(f"Buffer connection test failed: {e}")
            return {"connected": False, "error": str(e)}


# ── Singleton ────────────────────────────────────────────────

_buffer_instance: Optional[BufferClient] = None


def get_buffer_client(access_token: Optional[str] = None) -> BufferClient:
    """Factory — returns a Buffer client (singleton for default token, new for custom)."""
    global _buffer_instance
    if access_token:
        return BufferClient(access_token=access_token)
    if _buffer_instance is None:
        _buffer_instance = BufferClient()
    return _buffer_instance
