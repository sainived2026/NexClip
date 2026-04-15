"""
Nexearch — Metricool API Scraper
Pulls published posts and analytics directly from the Metricool REST API.
No browser automation needed — uses the authenticated API token.

Supports: instagram, tiktok, youtube, facebook, linkedin, twitter, threads
"""

import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from loguru import logger

from nexearch.tools.scrapers.base import BaseScraper, ScrapingResult
from nexearch.schemas.raw_post import RawPostCreate, PostMetrics


# ── Platform → Metricool endpoint/network mapping ─────────────────────────────

_PLATFORM_POST_ENDPOINTS: Dict[str, List[str]] = {
    "instagram":  ["/stats/instagram/reels", "/stats/instagram/posts"],
    "facebook":   ["/stats/facebook/posts"],
    "linkedin":   ["/stats/linkedin/posts"],
    "twitter":    [],  # Use analytics timeline only for Twitter
    "tiktok":     [],  # TikTok posts via analytics endpoint
    "youtube":    [],  # YouTube videos via analytics endpoint
    "threads":    [],  # Threads via analytics endpoint
}

_PLATFORM_NETWORK_NAME: Dict[str, str] = {
    "instagram": "instagram",
    "tiktok":    "tiktok",
    "youtube":   "youtube",
    "facebook":  "facebook",
    "linkedin":  "linkedin",
    "twitter":   "twitter",
    "threads":   "threads",
}

# Sortcolumn for each endpoint
_POST_SORT_COL: Dict[str, str] = {
    "/stats/instagram/reels": "engagement",
    "/stats/instagram/posts": "engagement",
    "/stats/facebook/posts":  "engagement",
    "/stats/linkedin/posts":  "engagement",
}


class MetricoolScraper(BaseScraper):
    """
    Scraper that pulls content + analytics directly from the Metricool API.

    Requires:
        metricool_api_key  — the X-Mc-Auth token
        user_id            — Metricool userId (from profile listing)
        blog_id            — Metricool brandId (blogId)

    If user_id/blog_id aren't stored in credentials yet, the scraper will
    call /admin/simpleProfiles to discover the correct brand from account_url.
    """

    def __init__(
        self,
        platform: str,
        client_id: str,
        api_token: str = "",
        user_id: str = "",
        blog_id: str = "",
        lookback_days: int = 90,
    ):
        super().__init__(platform, client_id)
        self._api_token = api_token
        self._user_id = user_id
        self._blog_id = blog_id
        self._lookback_days = lookback_days

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def scrape_method_name(self) -> str:
        return "metricool_api"

    async def check_availability(self) -> bool:
        return bool(self._api_token)

    async def refresh_metrics(
        self,
        account_url: str,
        post_ids: List[str],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Not supported for Metricool — returns empty dict."""
        return {}

    async def scrape(
        self,
        account_url: str,
        max_posts: int = 100,
        resume_cursor: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        since_date: Optional[datetime] = None,
    ) -> ScrapingResult:
        result = ScrapingResult()
        result.scrape_method = self.scrape_method_name

        if not self._api_token:
            result.add_error("MetricoolScraper: No API token configured")
            return result

        # Resolve user_id / blog_id if not provided
        if not self._blog_id or not self._user_id:
            creds = credentials or {}
            self._blog_id = self._blog_id or str(creds.get("metricool_blog_id", "") or "")
            self._user_id = self._user_id or str(creds.get("metricool_user_id", "") or "")

            if not self._blog_id or not self._user_id:
                resolved = await self._resolve_brand(account_url, credentials or {})
                if not resolved:
                    result.add_error(
                        f"MetricoolScraper: Could not find a Metricool profile matching "
                        f"account_url='{account_url}' for client '{self.client_id}'. "
                        "Ensure the account is connected to your Metricool brand."
                    )
                    return result
                self._blog_id, self._user_id = resolved

        # Date range
        end_dt = datetime.now(timezone.utc)
        start_dt = since_date or (end_dt - timedelta(days=self._lookback_days))
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")

        logger.info(
            f"[MetricoolScraper] Fetching {self.platform} content for client '{self.client_id}' "
            f"({start_str} → {end_str}), blog_id={self._blog_id}, user_id={self._user_id}"
        )

        endpoints = _PLATFORM_POST_ENDPOINTS.get(self.platform.lower(), [])

        all_raw_posts: List[Dict[str, Any]] = []

        if endpoints:
            # Platforms with direct /stats/... post list endpoints
            for endpoint in endpoints:
                try:
                    raw = await self._fetch_posts_endpoint(endpoint, start_str, end_str)
                    all_raw_posts.extend(raw)
                    logger.info(
                        f"[MetricoolScraper] {endpoint} returned {len(raw)} items"
                    )
                except Exception as exc:
                    err = f"MetricoolScraper: {endpoint} failed — {exc}"
                    result.add_error(err)
                    logger.warning(err)
        else:
            # Platforms without dedicated post list (TikTok, YouTube, Twitter, Threads)
            # Pull analytics timeline data to synthesize artificial post records
            try:
                timeline_posts = await self._fetch_timeline_fallback(start_str, end_str, max_posts)
                all_raw_posts.extend(timeline_posts)
                logger.info(
                    f"[MetricoolScraper] Timeline fallback returned {len(timeline_posts)} items "
                    f"for {self.platform}"
                )
            except Exception as exc:
                err = f"MetricoolScraper: timeline fallback failed for {self.platform} — {exc}"
                result.add_error(err)
                logger.warning(err)

        # Deduplicate by post_id
        seen_ids = set()
        unique_posts = []
        for p in all_raw_posts:
            pid = str(p.get("id") or p.get("postId") or p.get("uuid") or "")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                unique_posts.append(p)

        # Convert to RawPostCreate
        for raw_post in unique_posts[:max_posts]:
            try:
                post = self._convert_post(raw_post, account_url)
                result.add_post(post)
            except Exception as exc:
                logger.debug(f"[MetricoolScraper] Skip malformed post: {exc}")

        logger.info(
            f"[MetricoolScraper] Done: {result.total_scraped} posts for '{self.client_id}' on {self.platform}"
        )
        return result

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a Metricool API request with auth headers."""
        import httpx

        base_url = "https://app.metricool.com/api"
        url = f"{base_url}{endpoint}"

        # Metricool requires blogId + userId in query params on every request
        all_params: Dict[str, Any] = {
            "blogId": self._blog_id,
            "userId": self._user_id,
        }
        if params:
            all_params.update(params)

        headers = {
            "X-Mc-Auth": self._api_token,
            "Content-Type": "application/json",
        }

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.request(method, url, headers=headers, params=all_params)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "60"))
                    logger.warning(f"[MetricoolScraper] Rate limited. Waiting {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    continue

                if 200 <= resp.status_code < 300:
                    return resp.json() if resp.text else {}

                raise Exception(f"HTTP {resp.status_code}: {resp.text[:300]}")

            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

    async def _resolve_brand(
        self, account_url: str, creds: Dict[str, Any]
    ) -> Optional[tuple]:
        """Use /admin/simpleProfiles to find the matching blog_id + user_id."""
        try:
            from nexearch.tools.metricool import get_metricool_client
            client = get_metricool_client(access_token=self._api_token)
            profiles = await client.list_profiles()
            if not profiles:
                return None

            # Match by platform handle in account_url
            norm_url = account_url.lower().rstrip("/")
            for profile in profiles:
                platform_handle = str(profile.get(self.platform, "") or "").lower().strip()
                if platform_handle and platform_handle in norm_url:
                    blog_id = str(profile.get("id", ""))
                    user_id = str(profile.get("userId", ""))
                    if blog_id and user_id:
                        logger.info(
                            f"[MetricoolScraper] Resolved brand: blog_id={blog_id}, "
                            f"user_id={user_id} from profile label='{profile.get('label')}'"
                        )
                        return blog_id, user_id

            # Fallback: use the first profile
            first = profiles[0]
            blog_id = str(first.get("id", ""))
            user_id = str(first.get("userId", ""))
            if blog_id and user_id:
                logger.warning(
                    f"[MetricoolScraper] No exact match for '{account_url}'. "
                    f"Using first profile: {first.get('label')}"
                )
                return blog_id, user_id

        except Exception as exc:
            logger.error(f"[MetricoolScraper] _resolve_brand failed: {exc}")
        return None

    async def _fetch_posts_endpoint(
        self, endpoint: str, start: str, end: str
    ) -> List[Dict[str, Any]]:
        """Fetch posts from a /stats/.../posts endpoint."""
        sort_col = _POST_SORT_COL.get(endpoint, "engagement")
        data = await self._make_request(
            "GET",
            endpoint,
            params={"start": int(start), "end": int(end), "sortcolumn": sort_col},
        )
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("posts", []))
        return []

    async def _fetch_timeline_fallback(
        self, start: str, end: str, max_posts: int
    ) -> List[Dict[str, Any]]:
        """
        For platforms without post list endpoints (TikTok, YouTube, Twitter, Threads),
        pull the analytics timeline for engagement metrics in the date range.
        Returns synthetic post records with aggregated metrics per day.
        """
        network = _PLATFORM_NETWORK_NAME.get(self.platform, self.platform)

        # Pick a meaningful metric per platform
        metric_map = {
            "tiktok":  "interactions",
            "youtube": "interactions",
            "twitter": "interactions",
            "threads": "interactions",
        }
        metric = metric_map.get(self.platform, "interactions")

        try:
            data = await self._make_request(
                "GET",
                "/v2/analytics/timelines",
                params={
                    "network": network,
                    "metric": metric,
                    "from": start,
                    "to": end,
                },
            )
        except Exception as exc:
            logger.warning(f"[MetricoolScraper] Timeline endpoint failed: {exc}")
            return []

        # The response is a list of [date, value] pairs
        posts = []
        if isinstance(data, dict):
            data = data.get("data", [])

        for item in data or []:
            if isinstance(item, list) and len(item) >= 2:
                date_str, value = item[0], item[1]
                posts.append({
                    "id": f"{network}_{date_str}",
                    "postId": f"{network}_{date_str}",
                    "network": network,
                    "publishedDate": date_str,
                    "interactions": int(value or 0),
                    "_synthetic": True,
                })

        return posts

    def _convert_post(self, raw: Dict[str, Any], account_url: str) -> RawPostCreate:
        """Convert a Metricool API post dict to RawPostCreate."""
        import re

        post_id = str(
            raw.get("id") or raw.get("postId") or raw.get("uuid") or
            f"metricool_{self.platform}_{hash(str(raw))}"
        )

        # Detect posted_at
        posted_at = None
        for key in ("publishedDate", "created", "timestamp", "date"):
            val = raw.get(key)
            if val:
                try:
                    if isinstance(val, (int, float)):
                        # Unix timestamp in ms
                        posted_at = datetime.fromtimestamp(val / 1000, tz=timezone.utc)
                    else:
                        date_str = str(val).strip()
                        # Handle YYYYMMDD format
                        if re.match(r"^\d{8}$", date_str):
                            posted_at = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
                        else:
                            posted_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    break
                except Exception:
                    pass

        # Metrics
        likes       = int(raw.get("likes", 0) or 0)
        comments    = int(raw.get("comments", 0) or 0)
        shares      = int(raw.get("shares", 0) or 0) or None
        saves       = int(raw.get("saved", raw.get("saves", 0) or 0)) or None
        views       = int(raw.get("videoviews", raw.get("views", raw.get("videoViews", 0) or 0))) or None
        reach       = int(raw.get("reach", 0) or 0) or None
        impressions = int(raw.get("impressions", 0) or 0) or None
        interactions = int(raw.get("interactions", 0) or 0)

        metrics = PostMetrics(
            likes=likes,
            comments=comments,
            shares=shares,
            saves=saves,
            views=views,
            reach=reach,
            impressions=impressions,
        )

        # Caption / text
        caption = str(raw.get("text", raw.get("caption", raw.get("message", ""))) or "")

        # Post URL
        post_url = str(raw.get("url", raw.get("postUrl", account_url)) or account_url)

        # Format detection
        raw_format = str(raw.get("type", raw.get("format", raw.get("kind", ""))) or "").lower()
        fmt_map = {
            "reel": "reel", "reels": "reel",
            "video": "video", "videos": "video",
            "image": "image", "photo": "image", "carousel": "carousel",
            "story": "story", "stories": "story",
            "tweet": "tweet", "thread": "thread",
            "short": "short",
        }
        fmt = fmt_map.get(raw_format, "video" if views else "image")

        # Hashtags
        hashtags = [
            tag.lstrip("#")
            for tag in re.findall(r"#[\w\u00C0-\u024F]+", caption)
        ]

        # Engagement rate
        total_eng = likes + comments + (shares or 0) + (saves or 0) + interactions
        engagement_rate = self._compute_engagement_rate(
            likes=likes,
            comments=comments,
            shares=shares or 0,
            saves=saves,
            views=views,
        )

        day_of_week, hour_of_day = self._extract_day_hour(posted_at)

        return RawPostCreate(
            post_id=post_id,
            platform=self.platform,
            account_id=self._blog_id or self.client_id,
            url=post_url,
            format=fmt,
            caption=caption,
            hashtags=hashtags,
            posted_at=posted_at,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            metrics=metrics,
            engagement_rate=engagement_rate,
            scrape_method=self.scrape_method_name,
            raw_json=json.dumps(raw, default=str),
        )
