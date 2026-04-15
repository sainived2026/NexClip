"""
Nexearch — Platform API Scraper Backend
Uses official platform APIs with client access tokens.
Supports: Instagram Graph, YouTube Data, Twitter v2, Facebook Graph, Threads.
LinkedIn & TikTok fallback to Apify/Crawlee due to API restrictions.
"""

import asyncio
import httpx
import json
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from loguru import logger

from nexearch.tools.scrapers.base import BaseScraper, ScrapingResult
from nexearch.schemas.raw_post import RawPostCreate, PostMetrics


class PlatformAPIScraper(BaseScraper):
    """Scrapes via official platform APIs with user access tokens."""

    def __init__(self, platform: str, client_id: str, access_token: str = "",
                 page_id: str = "", api_key: str = ""):
        super().__init__(platform, client_id)
        self._access_token = access_token
        self._page_id = page_id
        self._api_key = api_key

    async def check_availability(self) -> bool:
        return bool(self._access_token) or bool(self._api_key)

    @property
    def scrape_method_name(self) -> str:
        return "platform_api"

    async def scrape(self, account_url: str, max_posts: int = 100,
                     resume_cursor: Optional[str] = None,
                     credentials: Optional[Dict[str, Any]] = None,
                     since_date: Optional[datetime] = None) -> ScrapingResult:
        result = ScrapingResult()
        result.scrape_method = "platform_api"
        token = (credentials or {}).get("access_token", self._access_token)
        page_id = (credentials or {}).get("page_id", self._page_id)
        api_key = (credentials or {}).get("api_key", self._api_key)

        try:
            dispatchers = {
                "instagram": lambda: self._scrape_ig(result, token, page_id, max_posts, resume_cursor),
                "youtube": lambda: self._scrape_yt(result, api_key or token, account_url, max_posts, resume_cursor),
                "twitter": lambda: self._scrape_tw(result, token, account_url, max_posts, resume_cursor),
                "facebook": lambda: self._scrape_fb(result, token, page_id, max_posts, resume_cursor),
                "threads": lambda: self._scrape_threads(result, token, page_id, max_posts, resume_cursor),
            }
            fn = dispatchers.get(self.platform)
            if fn:
                await fn()
            else:
                result.add_error(f"Platform API not yet supported for {self.platform} — use Apify or Crawlee")
        except Exception as e:
            result.add_error(f"Platform API scrape failed: {e}")
        return result

    async def refresh_metrics(self, account_url: str, post_ids: List[str],
                              credentials: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        result = await self.scrape(account_url, max_posts=len(post_ids) + 20, credentials=credentials)
        return {p.post_id: p.metrics.model_dump() for p in result.posts if p.post_id in post_ids}

    # ── Instagram Graph API ──────────────────────────────────

    async def _scrape_ig(self, result, token, page_id, max_posts, cursor):
        if not token:
            result.add_error("Instagram Graph API requires access token"); return
        ig_id = page_id or "me"
        url = f"https://graph.facebook.com/v19.0/{ig_id}/media"
        params = {"fields": "id,caption,media_type,media_url,thumbnail_url,timestamp,like_count,comments_count,permalink,video_url",
                  "limit": min(max_posts, 100), "access_token": token}
        if cursor: params["after"] = cursor
        collected = 0
        async with httpx.AsyncClient(timeout=30) as client:
            while collected < max_posts and url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    result.add_error(f"IG API error: {resp.status_code}"); break
                data = resp.json()
                for item in data.get("data", []):
                    post = self._parse_ig(item)
                    if post:
                        result.add_post(post); collected += 1
                        if collected >= max_posts: break
                paging = data.get("paging", {})
                url = paging.get("next"); params = {}
                result.resume_cursor = paging.get("cursors", {}).get("after", "")

    def _parse_ig(self, item):
        post_id = str(item.get("id", ""))
        posted_at = self._parse_dt(item.get("timestamp"))
        day, hour = self._extract_day_hour(posted_at)
        fmt_map = {"VIDEO": "reel", "CAROUSEL_ALBUM": "carousel", "IMAGE": "static_image"}
        likes = item.get("like_count", 0) or 0
        comments = item.get("comments_count", 0) or 0
        return RawPostCreate(
            post_id=post_id, platform="instagram", account_id="",
            url=item.get("permalink", ""), format=fmt_map.get(item.get("media_type", ""), "static_image"),
            caption=item.get("caption", "") or "", thumbnail_url=item.get("thumbnail_url", ""),
            video_url=item.get("video_url"), posted_at=posted_at, day_of_week=day, hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments),
            engagement_rate=self._compute_engagement_rate(likes, comments), scrape_method="platform_api",
            raw_json=json.dumps(item, default=str)[:5000])

    # ── YouTube Data API v3 ──────────────────────────────────

    async def _scrape_yt(self, result, api_key, account_url, max_posts, cursor):
        if not api_key:
            result.add_error("YouTube Data API requires API key"); return
        channel_id = account_url.rstrip("/").split("/")[-1]
        async with httpx.AsyncClient(timeout=30) as client:
            ch = await client.get("https://www.googleapis.com/youtube/v3/channels",
                                  params={"part": "contentDetails", "id": channel_id, "key": api_key})
            if ch.status_code != 200: result.add_error(f"YT channel lookup failed: {ch.status_code}"); return
            items = ch.json().get("items", [])
            if not items: result.add_error("YT channel not found"); return
            uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            page_token = cursor or ""
            collected = 0
            while collected < max_posts:
                params = {"part": "snippet", "playlistId": uploads,
                          "maxResults": min(50, max_posts - collected), "key": api_key}
                if page_token: params["pageToken"] = page_token
                pl = await client.get("https://www.googleapis.com/youtube/v3/playlistItems", params=params)
                if pl.status_code != 200: break
                pl_data = pl.json()
                vids = [i["snippet"]["resourceId"]["videoId"] for i in pl_data.get("items", [])
                        if i.get("snippet", {}).get("resourceId", {}).get("videoId")]
                if vids:
                    vr = await client.get("https://www.googleapis.com/youtube/v3/videos",
                                          params={"part": "snippet,statistics,contentDetails",
                                                  "id": ",".join(vids), "key": api_key})
                    if vr.status_code == 200:
                        for v in vr.json().get("items", []):
                            post = self._parse_yt(v)
                            if post: result.add_post(post); collected += 1
                page_token = pl_data.get("nextPageToken", "")
                result.resume_cursor = page_token
                if not page_token: break

    def _parse_yt(self, item):
        s = item.get("snippet", {}); st = item.get("statistics", {})
        cd = item.get("contentDetails", {})
        post_id = item.get("id", "")
        posted_at = self._parse_dt(s.get("publishedAt"))
        day, hour = self._extract_day_hour(posted_at)
        dur = self._parse_iso_duration(cd.get("duration", ""))
        fmt = "youtube_short" if dur and dur <= 60 else "youtube_video"
        views = int(st.get("viewCount", 0)); likes = int(st.get("likeCount", 0))
        comments = int(st.get("commentCount", 0))
        return RawPostCreate(
            post_id=post_id, platform="youtube", account_id=s.get("channelId", ""),
            url=f"https://www.youtube.com/watch?v={post_id}", format=fmt,
            title=s.get("title", ""), description=s.get("description", ""),
            caption=s.get("title", ""), hashtags=s.get("tags", []) or [],
            thumbnail_url=s.get("thumbnails", {}).get("high", {}).get("url", ""),
            duration_seconds=dur, posted_at=posted_at, day_of_week=day, hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, views=views),
            engagement_rate=self._compute_engagement_rate(likes, comments, views=views),
            scrape_method="platform_api", raw_json=json.dumps(item, default=str)[:5000])

    # ── Twitter API v2 ────────────────────────────────────────

    async def _scrape_tw(self, result, bearer, account_url, max_posts, cursor):
        if not bearer: result.add_error("Twitter API requires bearer token"); return
        handle = account_url.rstrip("/").split("/")[-1].lstrip("@")
        async with httpx.AsyncClient(timeout=30) as client:
            ur = await client.get(f"https://api.twitter.com/2/users/by/username/{handle}",
                                  headers={"Authorization": f"Bearer {bearer}"})
            if ur.status_code != 200: result.add_error(f"Twitter user lookup failed: {ur.status_code}"); return
            uid = ur.json().get("data", {}).get("id")
            if not uid: result.add_error("Twitter user not found"); return
            params = {"tweet.fields": "created_at,public_metrics,entities",
                      "max_results": min(100, max_posts)}
            if cursor: params["pagination_token"] = cursor
            tr = await client.get(f"https://api.twitter.com/2/users/{uid}/tweets",
                                  headers={"Authorization": f"Bearer {bearer}"}, params=params)
            if tr.status_code == 200:
                td = tr.json()
                for tw in td.get("data", []):
                    post = self._parse_tw(tw, handle)
                    if post: result.add_post(post)
                result.resume_cursor = td.get("meta", {}).get("next_token", "")

    def _parse_tw(self, item, handle):
        post_id = item.get("id", "")
        posted_at = self._parse_dt(item.get("created_at"))
        day, hour = self._extract_day_hour(posted_at)
        m = item.get("public_metrics", {})
        likes = m.get("like_count", 0); replies = m.get("reply_count", 0)
        rts = m.get("retweet_count", 0); quotes = m.get("quote_count", 0)
        imps = m.get("impression_count")
        ht = [h.get("tag", "") for h in item.get("entities", {}).get("hashtags", [])]
        return RawPostCreate(
            post_id=post_id, platform="twitter", account_id=handle,
            url=f"https://x.com/{handle}/status/{post_id}", format="tweet",
            caption=item.get("text", ""), hashtags=ht,
            posted_at=posted_at, day_of_week=day, hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=replies, shares=rts,
                                impressions=imps, replies=replies, retweets=rts, quotes=quotes),
            engagement_rate=self._compute_engagement_rate(likes, replies + rts, views=imps),
            scrape_method="platform_api", raw_json=json.dumps(item, default=str)[:5000])

    # ── Facebook Graph API ────────────────────────────────────

    async def _scrape_fb(self, result, token, page_id, max_posts, cursor):
        if not token or not page_id: result.add_error("Facebook requires token + page_id"); return
        params = {"fields": "id,message,created_time,type,permalink_url,shares,likes.summary(true),comments.summary(true)",
                  "limit": min(100, max_posts), "access_token": token}
        if cursor: params["after"] = cursor
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"https://graph.facebook.com/v19.0/{page_id}/posts", params=params)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", []):
                    post = self._parse_fb(item)
                    if post: result.add_post(post)
                result.resume_cursor = data.get("paging", {}).get("cursors", {}).get("after", "")

    def _parse_fb(self, item):
        post_id = item.get("id", "")
        posted_at = self._parse_dt(item.get("created_time"))
        day, hour = self._extract_day_hour(posted_at)
        likes = item.get("likes", {}).get("summary", {}).get("total_count", 0)
        comments = item.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares = item.get("shares", {}).get("count", 0)
        fmt = "facebook_video" if item.get("type") == "video" else "facebook_post"
        return RawPostCreate(
            post_id=post_id, platform="facebook", account_id="",
            url=item.get("permalink_url", ""), format=fmt,
            caption=item.get("message", "") or "",
            posted_at=posted_at, day_of_week=day, hour_of_day=hour,
            metrics=PostMetrics(likes=likes, comments=comments, shares=shares),
            engagement_rate=self._compute_engagement_rate(likes, comments, shares),
            scrape_method="platform_api", raw_json=json.dumps(item, default=str)[:5000])

    # ── Utilities ─────────────────────────────────────────────

    @staticmethod
    def _parse_dt(val) -> Optional[datetime]:
        if not val: return None
        try: return datetime.fromisoformat(str(val).replace("Z", "+00:00").replace("+0000", "+00:00"))
        except Exception: return None

    @staticmethod
    def _parse_iso_duration(d: str) -> Optional[float]:
        if not d or not d.startswith("PT"): return None
        h = re.search(r'(\d+)H', d); m = re.search(r'(\d+)M', d); s = re.search(r'(\d+)S', d)
        t = 0.0
        if h: t += int(h.group(1)) * 3600
        if m: t += int(m.group(1)) * 60
        if s: t += int(s.group(1))
        return t or None

    # ── Threads API ──────────────────────────────────────────

    async def _scrape_threads(self, result, token, user_id, max_posts, cursor):
        """Scrape posts via the Threads Graph API (Meta)."""
        if not token:
            result.add_error("Threads API requires access token (threads_basic permission)"); return
        threads_user_id = user_id or "me"
        fields = "id,media_type,media_url,text,timestamp,permalink,shortcode,is_quote_post"
        params = {
            "fields": fields,
            "limit": min(max_posts, 100),
            "access_token": token,
        }
        if cursor:
            params["after"] = cursor
        url = f"https://graph.threads.net/v1.0/{threads_user_id}/threads"
        collected = 0
        async with httpx.AsyncClient(timeout=30) as client:
            while collected < max_posts and url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    result.add_error(
                        f"Threads API error: {resp.status_code} — {resp.text[:200]}"
                    )
                    break
                data = resp.json()
                for item in data.get("data", []):
                    post = self._parse_threads_post(item)
                    if post:
                        result.add_post(post)
                        collected += 1
                        if collected >= max_posts:
                            break
                paging = data.get("paging", {})
                url = paging.get("next")
                params = {}  # next URL already has params
                result.resume_cursor = paging.get("cursors", {}).get("after", "")

    def _parse_threads_post(self, item):
        """Parse a single Threads post into RawPostCreate."""
        post_id = str(item.get("id", ""))
        posted_at = self._parse_dt(item.get("timestamp"))
        day, hour = self._extract_day_hour(posted_at)
        media_type = (item.get("media_type") or "").upper()
        if media_type == "VIDEO":
            fmt = "threads_video"
        elif media_type == "CAROUSEL_ALBUM":
            fmt = "threads_carousel"
        elif media_type == "IMAGE":
            fmt = "threads_image"
        else:
            fmt = "threads_text"
        return RawPostCreate(
            post_id=post_id,
            platform="threads",
            account_id="",
            url=item.get("permalink", ""),
            format=fmt,
            caption=item.get("text", "") or "",
            thumbnail_url=item.get("media_url", "") if media_type == "IMAGE" else "",
            video_url=item.get("media_url") if media_type == "VIDEO" else None,
            posted_at=posted_at,
            day_of_week=day,
            hour_of_day=hour,
            metrics=PostMetrics(likes=0, comments=0),
            engagement_rate=0.0,
            scrape_method="platform_api",
            raw_json=json.dumps(item, default=str)[:5000],
        )
