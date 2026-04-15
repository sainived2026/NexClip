"""
Nexearch — Publisher Base + Factory
Abstract publisher interface and factory for all 3 publishing methods.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class PublishResult:
    """Result of a publishing operation."""
    success: bool = False
    platform_post_id: str = ""
    platform_post_url: str = ""
    metricool_post_id: str = ""
    error_message: str = ""
    publish_method: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


SHORT_FORM_NETWORKS = {"instagram", "tiktok", "threads", "twitter"}


def _strip_trailing_hashtags(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").strip().splitlines()]
    while lines and lines[-1].strip().startswith("#"):
        lines.pop()
    return "\n".join(lines).strip()


def _compose_caption_text(
    *,
    platform: str,
    title: str = "",
    caption: str = "",
    hashtags: Optional[List[str]] = None,
) -> str:
    """Build the final caption text sent to a platform."""
    normalized_title = (title or "").strip()
    normalized_caption = _strip_trailing_hashtags(caption or "")
    segments: List[str] = []

    if platform in SHORT_FORM_NETWORKS and normalized_title:
        segments.append(normalized_title)

    if normalized_caption and normalized_caption != normalized_title:
        segments.append(normalized_caption)

    full_caption = "\n\n".join(segment for segment in segments if segment).strip()
    if hashtags:
        hashtag_line = " ".join(
            f"#{tag.lstrip('#')}" for tag in hashtags if str(tag).strip()
        )
        if hashtag_line:
            full_caption = f"{full_caption}\n\n{hashtag_line}".strip() if full_caption else hashtag_line

    return full_caption


class BasePublisher(ABC):
    """Abstract publisher interface."""

    def __init__(self, platform: str, client_id: str):
        self.platform = platform
        self.client_id = client_id
        self.logger = logger.bind(publisher=self.__class__.__name__, platform=platform)

    @abstractmethod
    async def publish(
        self,
        video_url: str,
        caption: str = "",
        title: str = "",
        description: str = "",
        hashtags: List[str] = [],
        schedule_at: Optional[str] = None,
        thumbnail_url: str = "",
        credentials: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> PublishResult:
        """Publish content to the target platform."""
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if this publishing backend is available."""
        pass

    @property
    @abstractmethod
    def publish_method_name(self) -> str:
        pass


class MetricoolPublisher(BasePublisher):
    """Publish via Metricool API."""

    def __init__(self, platform: str, client_id: str,
                 api_token: str = "", brand_id: str = "", profile_id: str = ""):
        super().__init__(platform, client_id)
        self._api_token = api_token
        self._brand_id = brand_id
        self._profile_id = profile_id

    async def check_availability(self) -> bool:
        from nexearch.tools.metricool import get_metricool_client
        client = get_metricool_client(access_token=self._api_token or None)
        return client.is_configured

    @property
    def publish_method_name(self) -> str:
        return "metricool"

    async def publish(self, video_url: str, caption: str = "", title: str = "",
                      description: str = "", hashtags: List[str] = [],
                      schedule_at: Optional[str] = None, thumbnail_url: str = "",
                      credentials: Optional[Dict[str, Any]] = None, **kwargs) -> PublishResult:
        from nexearch.tools.metricool import get_metricool_client
        from datetime import datetime, timezone

        result = PublishResult(publish_method="metricool")
        resolved_credentials = credentials or {}
        token = resolved_credentials.get("metricool_api_key", self._api_token)
        client = get_metricool_client(access_token=token or None)

        if not client.is_configured:
            result.error_message = "Metricool not configured"
            return result

        account_url = str(resolved_credentials.get("account_url", "") or "").strip()
        if not account_url:
            result.error_message = (
                f"Metricool publishing requires an account_url for client '{self.client_id}' on {self.platform}"
            )
            return result

        profile = await client.find_profile(
            account_url=account_url,
            account_handle=resolved_credentials.get("account_handle", self.client_id),
            platform=self.platform,
        )
        if not profile:
            try:
                available_profiles = await client.list_profiles()
            except Exception:
                available_profiles = []
            labels = [p.get("label") or str(p.get("id", "")) for p in available_profiles]
            result.error_message = (
                "Metricool token is connected, but no matching Metricool brand/profile was found "
                f"for client '{self.client_id}' on {self.platform}. Available profiles: {labels}"
            )
            return result
        brand_id = str(profile.get("id", ""))
        user_id = str(profile.get("userId") or resolved_credentials.get("user_id") or "").strip()
        if not user_id:
            result.error_message = (
                f"Metricool profile '{brand_id}' is missing userId, so publishing cannot continue"
            )
            return result

        full_caption = _compose_caption_text(
            platform=self.platform,
            title=title,
            caption=caption,
            hashtags=hashtags,
        )
        publish_date = schedule_at or datetime.now(timezone.utc).isoformat()
        resolved_video_url = (video_url or "").strip()
        if resolved_video_url and not resolved_video_url.startswith(("http://", "https://")):
            local_video_path = Path(resolved_video_url)
            if local_video_path.exists():
                resolved_video_url = await client.upload_media_file(str(local_video_path))

        # Map platform to Metricool network name
        network_map = {
            "instagram": "instagram", "tiktok": "tiktok", "youtube": "youtube",
            "twitter": "twitter", "linkedin": "linkedin", "facebook": "facebook",
            "threads": "threads",
        }
        network = network_map.get(self.platform, self.platform)

        try:
            resp = await client.add_post(
                brand_id=brand_id, user_id=user_id, network=network, text=full_caption,
                publish_date=publish_date, video_url=resolved_video_url,
                thumbnail_url=thumbnail_url or None, title=title or None,
            )
            result.success = True
            result.metricool_post_id = str(resp.get("id", resp.get("uuid", resp.get("postId", ""))))
            result.raw_response = resp
            self.logger.info(f"Published via Metricool: {result.metricool_post_id}")
        except Exception as e:
            result.error_message = str(e)
            self.logger.error(f"Metricool publish failed: {e}")

        return result


class PlatformAPIPublisher(BasePublisher):
    """Publish via official platform APIs."""

    def __init__(self, platform: str, client_id: str,
                 access_token: str = "", page_id: str = ""):
        super().__init__(platform, client_id)
        self._access_token = access_token
        self._page_id = page_id

    async def check_availability(self) -> bool:
        return bool(self._access_token)

    @property
    def publish_method_name(self) -> str:
        return "platform_api"

    async def publish(self, video_url: str, caption: str = "", title: str = "",
                      description: str = "", hashtags: List[str] = [],
                      schedule_at: Optional[str] = None, thumbnail_url: str = "",
                      credentials: Optional[Dict[str, Any]] = None, **kwargs) -> PublishResult:
        import httpx
        result = PublishResult(publish_method="platform_api")
        token = (credentials or {}).get("access_token", self._access_token)

        if not token:
            result.error_message = "No access token provided"
            return result

        try:
            if self.platform == "youtube":
                result = await self._publish_youtube(result, token, video_url, title, description, hashtags)
            elif self.platform == "twitter":
                result.error_message = "Twitter video upload requires OAuth 1.0a — use Metricool"
            elif self.platform == "instagram":
                result = await self._publish_instagram(result, token, video_url, caption, hashtags)
            elif self.platform == "facebook":
                result = await self._publish_facebook(result, token, video_url, caption, title)
            elif self.platform == "threads":
                result = await self._publish_threads(result, token, video_url, caption)
            else:
                result.error_message = f"Platform API publishing not yet supported for {self.platform}"
        except Exception as e:
            result.error_message = str(e)

        return result

    async def _publish_instagram(self, result, token, video_url, caption, hashtags):
        """Instagram Content Publishing API (requires Business account)."""
        import httpx
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Create media container
            create_resp = await client.post(
                f"https://graph.facebook.com/v19.0/{self._page_id}/media",
                params={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": full_caption,
                    "access_token": token,
                },
            )
            if create_resp.status_code != 200:
                result.error_message = f"IG container creation failed: {create_resp.text[:200]}"
                return result

            container_id = create_resp.json().get("id")

            # Step 2: Publish the container
            pub_resp = await client.post(
                f"https://graph.facebook.com/v19.0/{self._page_id}/media_publish",
                params={"creation_id": container_id, "access_token": token},
            )
            if pub_resp.status_code == 200:
                result.success = True
                result.platform_post_id = pub_resp.json().get("id", "")
            else:
                result.error_message = f"IG publish failed: {pub_resp.text[:200]}"

        return result

    async def _publish_youtube(self, result, token, video_url, title, description, hashtags):
        """YouTube Data API video upload."""
        result.error_message = "YouTube API video upload requires resumable upload — use Metricool"
        return result

    async def _publish_facebook(self, result, token, video_url, caption, title):
        """Facebook Graph API video publish."""
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://graph.facebook.com/v19.0/{self._page_id}/videos",
                params={"file_url": video_url, "description": caption,
                        "title": title, "access_token": token},
            )
            if resp.status_code == 200:
                result.success = True
                result.platform_post_id = resp.json().get("id", "")
            else:
                result.error_message = f"FB publish failed: {resp.text[:200]}"
        return result

    async def _publish_threads(self, result, token, video_url, caption):
        """Threads API two-step video publish."""
        import httpx
        page_id = self._page_id or "me"
        async with httpx.AsyncClient(timeout=120) as client:
            # Step 1: Create media container
            create_resp = await client.post(
                f"https://graph.threads.net/v1.0/{page_id}/threads",
                params={
                    "media_type": "VIDEO",
                    "video_url": video_url,
                    "text": caption,
                    "access_token": token,
                },
            )
            if create_resp.status_code != 200:
                result.error_message = f"Threads container creation failed: {create_resp.text[:200]}"
                return result

            creation_id = create_resp.json().get("id")
            if not creation_id:
                result.error_message = "Threads container ID missing"
                return result

            # Wait for video processing (recommended 30s)
            import asyncio
            await asyncio.sleep(30)

            # Step 2: Publish
            pub_resp = await client.post(
                f"https://graph.threads.net/v1.0/{page_id}/threads_publish",
                params={"creation_id": creation_id, "access_token": token},
            )
            if pub_resp.status_code == 200:
                result.success = True
                result.platform_post_id = pub_resp.json().get("id", "")
                self.logger.info(f"Published to Threads: {result.platform_post_id}")
            else:
                result.error_message = f"Threads publish failed: {pub_resp.text[:200]}"

        return result


class CrawleePublisher(BasePublisher):
    """Publish via Playwright browser automation (anti-bot detection)."""

    def __init__(self, platform: str, client_id: str, headless: bool = False):
        super().__init__(platform, client_id)
        self._headless = headless

    async def check_availability(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False

    @property
    def publish_method_name(self) -> str:
        return "crawlee_playwright"

    async def publish(self, video_url: str, caption: str = "", title: str = "",
                      description: str = "", hashtags: List[str] = [],
                      schedule_at: Optional[str] = None, thumbnail_url: str = "",
                      credentials: Optional[Dict[str, Any]] = None, **kwargs) -> PublishResult:
        from nexearch.tools.publishers.playwright_publisher import PlaywrightPublisher

        result = PublishResult(publish_method="crawlee_playwright")

        # Build full caption with hashtags
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        pw_publisher = PlaywrightPublisher(self.platform, headless=self._headless)
        pw_result = await pw_publisher.publish(
            video_path=video_url,  # For Playwright, this must be a local file path
            caption=full_caption,
            title=title,
            description=description,
            credentials=credentials,
        )

        result.success = pw_result.get("success", False)
        result.error_message = pw_result.get("error", "")
        result.raw_response = pw_result

        if result.success:
            self.logger.info(f"Published via Playwright to {self.platform}")
        else:
            self.logger.error(f"Playwright publish failed: {result.error_message}")

        return result


class BufferPublisher(BasePublisher):
    """Publish via Buffer API."""

    def __init__(self, platform: str, client_id: str,
                 buffer_access_token: str = ""):
        super().__init__(platform, client_id)
        self._buffer_token = buffer_access_token

    async def check_availability(self) -> bool:
        if self._buffer_token:
            return True
        from nexearch.config import get_nexearch_settings
        return bool(get_nexearch_settings().BUFFER_ACCESS_TOKEN)

    @property
    def publish_method_name(self) -> str:
        return "buffer"

    async def publish(self, video_url: str, caption: str = "", title: str = "",
                      description: str = "", hashtags: List[str] = [],
                      schedule_at: Optional[str] = None, thumbnail_url: str = "",
                      credentials: Optional[Dict[str, Any]] = None, **kwargs) -> PublishResult:
        from nexearch.tools.buffer import get_buffer_client

        result = PublishResult(publish_method="buffer")
        token = (credentials or {}).get("buffer_api_key", self._buffer_token)

        if not token:
            result.error_message = "No Buffer access token provided"
            return result

        client = get_buffer_client(access_token=token)

        # Build full caption
        full_caption = caption
        if hashtags:
            full_caption += "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)

        try:
            # Get profile IDs for this platform
            profiles = await client.get_profiles_for_platform(self.platform)
            if not profiles:
                result.error_message = (
                    f"No Buffer profile connected for {self.platform}. "
                    f"Connect {self.platform} in your Buffer dashboard first."
                )
                return result

            profile_ids = [p["id"] for p in profiles if p.get("id")]

            media = {}
            if video_url:
                media["video"] = video_url
            if thumbnail_url:
                media["thumbnail"] = thumbnail_url
            if title:
                media["title"] = title
            if description:
                media["description"] = description

            resp = await client.create_post(
                profile_ids=profile_ids,
                text=full_caption,
                media=media if media else None,
                scheduled_at=schedule_at,
                now=not schedule_at,
            )

            result.success = resp.get("success", True)
            result.platform_post_id = str(resp.get("updates", [{}])[0].get("id", "") if resp.get("updates") else "")
            result.raw_response = resp
            self.logger.info(f"Published via Buffer to {self.platform}")

        except Exception as e:
            result.error_message = str(e)
            self.logger.error(f"Buffer publish failed: {e}")

        return result


# ── Factory ───────────────────────────────────────────────────────

def create_publisher(method: str, platform: str, client_id: str, **kwargs) -> BasePublisher:
    """Create the appropriate publisher based on method."""
    if method == "metricool":
        return MetricoolPublisher(platform, client_id,
                                 api_token=kwargs.get("metricool_api_key", ""),
                                 brand_id=kwargs.get("brand_id", ""),
                                 profile_id=kwargs.get("profile_id", ""))
    elif method == "platform_api":
        return PlatformAPIPublisher(platform, client_id,
                                     access_token=kwargs.get("access_token", ""),
                                     page_id=kwargs.get("page_id", ""))
    elif method == "crawlee_playwright":
        return CrawleePublisher(platform, client_id)
    elif method == "buffer":
        return BufferPublisher(platform, client_id,
                                buffer_access_token=kwargs.get("buffer_api_key", kwargs.get("buffer_access_token", "")))
    else:
        logger.warning(f"Unknown publishing method '{method}', defaulting to Metricool")
        return MetricoolPublisher(platform, client_id)
