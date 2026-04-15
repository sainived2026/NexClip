"""
Nexearch — Apify Scraper Backend
Uses Apify actors/scrapers via their REST API.
Supports Instagram, TikTok, YouTube, Twitter, LinkedIn, Facebook, Threads.
"""

import asyncio
import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from loguru import logger
import json

from nexearch.config import get_nexearch_settings
from nexearch.tools.scrapers.base import BaseScraper, ScrapingResult
from nexearch.schemas.raw_post import RawPostCreate, PostMetrics


# Apify actor IDs for each platform
APIFY_ACTORS = {
    "instagram": "apify/instagram-profile-scraper",
    "tiktok": "clockworks/tiktok-scraper",
    "youtube": "bernardo/youtube-scraper",
    "twitter": "apidojo/tweet-scraper",
    "linkedin": "anchor/linkedin-scraper",
    "facebook": "apify/facebook-pages-scraper",
    "threads": "apify/threads-scraper",
}


class ApifyScraper(BaseScraper):
    """
    Scrapes social media accounts via Apify REST API.
    Each platform maps to a specific Apify actor/scraper.
    Requires APIFY_API_KEY in .env configuration.
    """

    def __init__(self, platform: str, client_id: str):
        super().__init__(platform, client_id)
        self._settings = get_nexearch_settings()
        self._api_key = self._settings.APIFY_API_KEY
        self._base_url = "https://api.apify.com/v2"

    async def check_availability(self) -> bool:
        """Check if Apify API key is configured and valid."""
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base_url}/users/me",
                    params={"token": self._api_key},
                )
                return resp.status_code == 200
        except Exception:
            return False

    @property
    def scrape_method_name(self) -> str:
        return "apify"

    async def scrape(
        self,
        account_url: str,
        max_posts: int = 100,
        resume_cursor: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        since_date: Optional[datetime] = None,
    ) -> ScrapingResult:
        """Scrape posts using the appropriate Apify actor."""
        result = ScrapingResult()
        result.scrape_method = "apify"

        if not self._api_key:
            result.add_error("Apify API key not configured")
            return result

        actor_id = APIFY_ACTORS.get(self.platform)
        if not actor_id:
            result.add_error(f"No Apify actor configured for platform: {self.platform}")
            return result

        start_time = asyncio.get_event_loop().time()

        try:
            # Build actor input based on platform
            actor_input = self._build_actor_input(account_url, max_posts, since_date)

            # Run the actor
            run_data = await self._run_actor(actor_id, actor_input)

            if not run_data:
                result.add_error("Apify actor run returned no data")
                return result

            # Get the dataset items
            dataset_id = run_data.get("defaultDatasetId")
            if not dataset_id:
                result.add_error("No dataset ID returned from Apify run")
                return result

            items = await self._get_dataset_items(dataset_id, max_posts)

            # Parse items into RawPostCreate objects
            for item in items:
                try:
                    post = self._parse_item(item)
                    if post:
                        result.add_post(post)
                except Exception as e:
                    result.add_error(f"Failed to parse item: {e}")
                    continue

            self.logger.info(f"Apify scrape complete: {result.total_scraped} posts from {account_url}")

        except Exception as e:
            result.add_error(f"Apify scrape failed: {e}")
            self.logger.error(f"Apify scrape error: {e}")

        result.duration_seconds = asyncio.get_event_loop().time() - start_time
        return result

    async def refresh_metrics(
        self,
        account_url: str,
        post_ids: List[str],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Refresh metrics by re-scraping specific posts."""
        # For Apify, we re-run a scrape and match by post_id
        result = await self.scrape(account_url, max_posts=len(post_ids) + 20)
        metrics_map = {}
        for post in result.posts:
            if post.post_id in post_ids:
                metrics_map[post.post_id] = post.metrics.model_dump()
        return metrics_map

    # ── Private Methods ──────────────────────────────────────

    def _build_actor_input(
        self,
        account_url: str,
        max_posts: int,
        since_date: Optional[datetime],
    ) -> Dict[str, Any]:
        """Build platform-specific actor input."""
        base_input = {
            "resultsLimit": max_posts,
        }

        if self.platform == "instagram":
            # Extract username from URL
            handle = account_url.rstrip("/").split("/")[-1].lstrip("@")
            base_input.update({
                "directUrls": [account_url],
                "resultsType": "posts",
                "maxPosts": max_posts,
                "loginUsername": "clipaura2026@gmail.com",
                "loginPassword": "ClipAura.com",
            })
        elif self.platform == "tiktok":
            base_input.update({
                "profiles": [account_url],
                "resultsPerPage": max_posts,
            })
        elif self.platform == "youtube":
            base_input.update({
                "startUrls": [{"url": account_url}],
                "maxResults": max_posts,
            })
        elif self.platform == "twitter":
            handle = account_url.rstrip("/").split("/")[-1].lstrip("@")
            base_input.update({
                "twitterHandles": [handle],
                "maxTweets": max_posts,
            })
        elif self.platform == "linkedin":
            base_input.update({
                "urls": [account_url],
                "maxPosts": max_posts,
            })
        elif self.platform == "facebook":
            base_input.update({
                "startUrls": [{"url": account_url}],
                "maxPosts": max_posts,
            })
        elif self.platform == "threads":
            handle = account_url.rstrip("/").split("/")[-1].lstrip("@")
            base_input.update({
                "directUrls": [account_url],
                "resultsType": "posts",
                "maxPosts": max_posts,
            })

        if since_date:
            base_input["sinceDate"] = since_date.isoformat()

        return base_input

    async def _run_actor(self, actor_id: str, input_data: Dict) -> Optional[Dict]:
        """Start an Apify actor run and wait for completion."""
        url = f"{self._base_url}/acts/{actor_id}/runs"
        async with httpx.AsyncClient(timeout=300) as client:
            # Start the run
            resp = await client.post(
                url,
                params={"token": self._api_key},
                json=input_data,
            )
            if resp.status_code != 201:
                self.logger.error(f"Apify actor start failed: {resp.status_code} - {resp.text[:200]}")
                return None

            run_info = resp.json().get("data", {})
            run_id = run_info.get("id")

            if not run_id:
                return None

            # Poll for completion
            for _ in range(120):  # Max 10 minutes
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"{self._base_url}/actor-runs/{run_id}",
                    params={"token": self._api_key},
                )
                if status_resp.status_code == 200:
                    run_data = status_resp.json().get("data", {})
                    status = run_data.get("status")
                    if status == "SUCCEEDED":
                        return run_data
                    elif status in ("FAILED", "TIMED-OUT", "ABORTED"):
                        self.logger.error(f"Apify actor run {status}: {run_data.get('statusMessage', '')}")
                        return None

            self.logger.error("Apify actor run timed out after 10 minutes")
            return None

    async def _get_dataset_items(self, dataset_id: str, limit: int) -> List[Dict]:
        """Fetch items from an Apify dataset."""
        url = f"{self._base_url}/datasets/{dataset_id}/items"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                url,
                params={"token": self._api_key, "limit": limit, "format": "json"},
            )
            if resp.status_code == 200:
                return resp.json()
        return []

    def _parse_item(self, item: Dict) -> Optional[RawPostCreate]:
        """Parse an Apify item into a RawPostCreate based on platform."""
        try:
            if self.platform == "instagram":
                return self._parse_instagram(item)
            elif self.platform == "tiktok":
                return self._parse_tiktok(item)
            elif self.platform == "youtube":
                return self._parse_youtube(item)
            elif self.platform == "twitter":
                return self._parse_twitter(item)
            elif self.platform == "linkedin":
                return self._parse_linkedin(item)
            elif self.platform == "facebook":
                return self._parse_facebook(item)
            elif self.platform == "threads":
                return self._parse_threads(item)
        except Exception as e:
            self.logger.warning(f"Parse error for {self.platform}: {e}")
        return None

    def _parse_instagram(self, item: Dict) -> RawPostCreate:
        """Parse an Instagram post from Apify data."""
        post_id = str(item.get("id", item.get("shortCode", "")))
        posted_at = None
        if item.get("timestamp"):
            try:
                posted_at = datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00"))
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        likes = item.get("likesCount", 0) or 0
        comments = item.get("commentsCount", 0) or 0
        views = item.get("videoViewCount") or item.get("videoPlayCount")

        # Determine format
        post_type = item.get("type", "")
        if post_type == "Video" or item.get("isVideo"):
            fmt = "reel"
        elif post_type == "Sidecar":
            fmt = "carousel"
        else:
            fmt = "static_image"

        return RawPostCreate(
            post_id=post_id,
            platform="instagram",
            account_id=item.get("ownerUsername", ""),
            url=item.get("url", f"https://www.instagram.com/p/{item.get('shortCode', '')}/"),
            format=fmt,
            caption=item.get("caption", "") or "",
            hashtags=item.get("hashtags", []) or [],
            mentions=item.get("mentions", []) or [],
            thumbnail_url=item.get("displayUrl", ""),
            video_url=item.get("videoUrl"),
            duration_seconds=item.get("videoDuration"),
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(
                likes=likes,
                comments=comments,
                views=views,
            ),
            engagement_rate=self._compute_engagement_rate(likes, comments, views=views),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )

    def _parse_tiktok(self, item: Dict) -> RawPostCreate:
        """Parse a TikTok post from Apify data."""
        post_id = str(item.get("id", ""))
        posted_at = None
        create_time = item.get("createTime")
        if create_time:
            try:
                posted_at = datetime.fromtimestamp(int(create_time), tz=timezone.utc)
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        stats = item.get("stats", {}) or {}
        likes = stats.get("diggCount", 0) or 0
        comments = stats.get("commentCount", 0) or 0
        shares = stats.get("shareCount", 0) or 0
        views = stats.get("playCount", 0) or 0

        return RawPostCreate(
            post_id=post_id,
            platform="tiktok",
            account_id=item.get("author", {}).get("uniqueId", ""),
            url=f"https://www.tiktok.com/@{item.get('author', {}).get('uniqueId', '')}/video/{post_id}",
            format="tiktok_video",
            caption=item.get("desc", "") or "",
            hashtags=[t.get("title", "") for t in item.get("challenges", []) if t.get("title")],
            audio_name=item.get("music", {}).get("title"),
            audio_is_original=item.get("music", {}).get("original", False),
            duration_seconds=item.get("video", {}).get("duration"),
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, shares=shares, views=views),
            engagement_rate=self._compute_engagement_rate(likes, comments, shares, views=views),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )

    def _parse_youtube(self, item: Dict) -> RawPostCreate:
        """Parse a YouTube video from Apify data."""
        post_id = str(item.get("id", item.get("videoId", "")))
        posted_at = None
        if item.get("date") or item.get("uploadDate"):
            try:
                date_str = item.get("date") or item.get("uploadDate")
                posted_at = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        views = item.get("viewCount", 0) or 0
        likes = item.get("likes", 0) or 0
        comments = item.get("commentsCount", 0) or 0
        duration = item.get("duration")

        # Determine format
        dur_seconds = None
        if duration:
            try:
                dur_seconds = float(duration)
            except (ValueError, TypeError):
                pass
        fmt = "youtube_short" if dur_seconds and dur_seconds <= 60 else "youtube_video"

        return RawPostCreate(
            post_id=post_id,
            platform="youtube",
            account_id=item.get("channelName", item.get("channelId", "")),
            url=item.get("url", f"https://www.youtube.com/watch?v={post_id}"),
            format=fmt,
            title=item.get("title", "") or "",
            description=item.get("description", "") or "",
            caption=item.get("title", "") or "",
            hashtags=item.get("hashtags", []) or [],
            thumbnail_url=item.get("thumbnailUrl", ""),
            duration_seconds=dur_seconds,
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, views=views),
            engagement_rate=self._compute_engagement_rate(likes, comments, views=views),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )

    def _parse_twitter(self, item: Dict) -> RawPostCreate:
        """Parse a Twitter/X post from Apify data."""
        post_id = str(item.get("id", item.get("tweetId", "")))
        posted_at = None
        if item.get("createdAt"):
            try:
                posted_at = datetime.fromisoformat(str(item["createdAt"]).replace("Z", "+00:00"))
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        likes = item.get("likeCount", item.get("favoriteCount", 0)) or 0
        replies = item.get("replyCount", 0) or 0
        retweets = item.get("retweetCount", 0) or 0
        quotes = item.get("quoteCount", 0) or 0
        views = item.get("viewCount", item.get("impressionCount")) or None

        return RawPostCreate(
            post_id=post_id,
            platform="twitter",
            account_id=item.get("author", {}).get("userName", item.get("userName", "")),
            url=item.get("url", f"https://x.com/i/status/{post_id}"),
            format="tweet",
            caption=item.get("text", item.get("fullText", "")) or "",
            hashtags=item.get("hashtags", []) or [],
            mentions=item.get("mentions", []) or [],
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(
                likes=likes, comments=replies, shares=retweets,
                views=views, replies=replies, retweets=retweets, quotes=quotes,
            ),
            engagement_rate=self._compute_engagement_rate(likes, replies + retweets, views=views),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )

    def _parse_linkedin(self, item: Dict) -> RawPostCreate:
        """Parse a LinkedIn post from Apify data."""
        post_id = str(item.get("id", item.get("activityId", "")))
        posted_at = None
        if item.get("postedDate"):
            try:
                posted_at = datetime.fromisoformat(str(item["postedDate"]).replace("Z", "+00:00"))
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        likes = item.get("numLikes", 0) or 0
        comments = item.get("numComments", 0) or 0
        shares = item.get("numShares", 0) or 0

        fmt = "linkedin_video" if item.get("video") else "linkedin_post"

        return RawPostCreate(
            post_id=post_id,
            platform="linkedin",
            account_id=item.get("authorProfileUrl", ""),
            url=item.get("postUrl", ""),
            format=fmt,
            caption=item.get("text", "") or "",
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, shares=shares),
            engagement_rate=self._compute_engagement_rate(likes, comments, shares),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )

    def _parse_facebook(self, item: Dict) -> RawPostCreate:
        """Parse a Facebook post from Apify data."""
        post_id = str(item.get("postId", item.get("id", "")))
        posted_at = None
        if item.get("time"):
            try:
                posted_at = datetime.fromisoformat(str(item["time"]).replace("Z", "+00:00"))
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        likes = item.get("likes", 0) or 0
        comments = item.get("comments", 0) or 0
        shares = item.get("shares", 0) or 0
        views = item.get("videoViews") or None

        fmt = "facebook_video" if item.get("isVideo") or item.get("videoUrl") else "facebook_post"

        return RawPostCreate(
            post_id=post_id,
            platform="facebook",
            account_id=item.get("pageName", ""),
            url=item.get("postUrl", item.get("url", "")),
            format=fmt,
            caption=item.get("text", item.get("message", "")) or "",
            title=item.get("title", "") or "",
            video_url=item.get("videoUrl"),
            thumbnail_url=item.get("imageUrl"),
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, shares=shares, views=views),
            engagement_rate=self._compute_engagement_rate(likes, comments, shares, views=views),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )

    def _parse_threads(self, item: Dict) -> RawPostCreate:
        """Parse a Threads post from Apify data."""
        post_id = str(item.get("id", item.get("shortCode", "")))
        posted_at = None
        if item.get("timestamp") or item.get("createdAt"):
            try:
                dt_str = item.get("timestamp") or item.get("createdAt")
                posted_at = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            except Exception:
                pass

        day, hour = self._extract_day_hour(posted_at)
        likes = item.get("likesCount", item.get("likes", 0)) or 0
        comments = item.get("commentsCount", item.get("comments", 0)) or 0
        views = item.get("viewCount") or None

        media_type = (item.get("mediaType", item.get("type", ""))).upper()
        if "VIDEO" in media_type or item.get("isVideo"):
            fmt = "threads_video"
        elif "CAROUSEL" in media_type or "SIDECAR" in media_type:
            fmt = "threads_carousel"
        elif "IMAGE" in media_type:
            fmt = "threads_image"
        else:
            fmt = "threads_text"

        return RawPostCreate(
            post_id=post_id,
            platform="threads",
            account_id=item.get("ownerUsername", item.get("username", "")),
            url=item.get("url", item.get("permalink", "")),
            format=fmt,
            caption=item.get("text", item.get("caption", "")) or "",
            hashtags=item.get("hashtags", []) or [],
            thumbnail_url=item.get("displayUrl", item.get("imageUrl", "")),
            video_url=item.get("videoUrl"),
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, views=views),
            engagement_rate=self._compute_engagement_rate(likes, comments, views=views),
            scrape_method="apify",
            raw_json=json.dumps(item, default=str)[:5000],
        )
