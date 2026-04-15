"""
Nexearch - Crawlee + Playwright Scraper Backend
Browser-based scraping using Playwright for platforms that resist API/Apify.
Supports all 6 platforms with headless Chrome automation.
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote, urljoin, urlparse

from loguru import logger

from nexearch.config import get_nexearch_settings
from nexearch.schemas.raw_post import PostMetrics, RawPostCreate
from nexearch.tools.scrapers.base import BaseScraper, ScrapingResult


class CrawleePlaywrightScraper(BaseScraper):
    """
    Browser-based scraper using Playwright for direct page scraping.
    Best for: accounts that block API access, or when Apify isn't available.
    Uses headless Chrome with configurable concurrency and delays.
    """

    def __init__(self, platform: str, client_id: str):
        super().__init__(platform, client_id)
        self._settings = get_nexearch_settings()
        self._headless = self._settings.CRAWLEE_HEADLESS
        self._max_concurrency = self._settings.CRAWLEE_MAX_CONCURRENCY
        self._timeout = self._settings.CRAWLEE_REQUEST_TIMEOUT_SECONDS * 1000
        self._delay_min = self._settings.SCRAPER_DELAY_MIN_SECONDS
        self._delay_max = self._settings.SCRAPER_DELAY_MAX_SECONDS

    async def check_availability(self) -> bool:
        try:
            from playwright.async_api import async_playwright  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def scrape_method_name(self) -> str:
        return "crawlee_playwright"

    async def scrape(
        self,
        account_url: str,
        max_posts: int = 100,
        resume_cursor: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        since_date: Optional[datetime] = None,
    ) -> ScrapingResult:
        result = ScrapingResult()
        result.scrape_method = "crawlee_playwright"
        result.metadata = credentials or {}
        start = asyncio.get_event_loop().time()

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            result.add_error(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
            return result

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self._headless)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                    ),
                )

                if credentials and credentials.get("cookies"):
                    await context.add_cookies(credentials["cookies"])

                page = await context.new_page()
                page.set_default_timeout(self._timeout)

                dispatchers = {
                    "instagram": self._scrape_ig_browser,
                    "tiktok": self._scrape_tiktok_browser,
                    "youtube": self._scrape_yt_browser,
                    "twitter": self._scrape_tw_browser,
                    "linkedin": self._scrape_linkedin_browser,
                    "facebook": self._scrape_fb_browser,
                }

                fn = dispatchers.get(self.platform)
                if fn:
                    await fn(page, account_url, max_posts, result)
                else:
                    result.add_error(f"Browser scraping not implemented for {self.platform}")

                await browser.close()

        except Exception as e:
            result.add_error(f"Playwright scrape failed: {e}")
            self.logger.error(f"Crawlee error: {e}")

        result.duration_seconds = asyncio.get_event_loop().time() - start
        return result

    async def refresh_metrics(
        self,
        account_url: str,
        post_ids: List[str],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        result = await self.scrape(account_url, max_posts=len(post_ids) + 20, credentials=credentials)
        return {p.post_id: p.metrics.model_dump() for p in result.posts if p.post_id in post_ids}

    async def _scrape_ig_browser(self, page, url, max_posts, result):
        """Scrape Instagram profile by scrolling and extracting post data."""
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        if await page.query_selector('input[name="username"]'):
            username = ""
            password = ""
            if isinstance(result.metadata, dict):
                username = result.metadata.get("login_username", "")
                password = result.metadata.get("login_password", "")

            logger.info("Instagram login required. Attempting to use configured credentials...")
            if not username or not password:
                result.add_error("Instagram login required but no client login credentials were provided")
                result.was_blocked = True
                return

            try:
                await page.fill('input[name="username"]', username)
                await page.fill('input[name="password"]', password)
                await page.click('button[type="submit"]')
                await asyncio.sleep(6)

                if await page.query_selector('input[name="username"]'):
                    result.add_error("Instagram login failed or required 2FA/verification")
                    result.was_blocked = True
                    return
            except Exception as e:
                result.add_error(f"Failed Instagram login automation: {e}")
                result.was_blocked = True
                return

        post_links = set()
        scroll_attempts = 0
        max_scrolls = max_posts // 4 + 10

        while len(post_links) < max_posts and scroll_attempts < max_scrolls:
            links = await page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    post_links.add(href)

            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(self._random_delay())
            scroll_attempts += 1

        for link in list(post_links)[:max_posts]:
            try:
                full_url = f"https://www.instagram.com{link}" if link.startswith("/") else link
                await page.goto(full_url, wait_until="domcontentloaded")
                await asyncio.sleep(1.5)

                post = await self._extract_ig_post(page, full_url)
                if post:
                    result.add_post(post)
            except Exception as e:
                result.add_error(f"Failed to extract IG post {link}: {e}")

    async def _extract_ig_post(self, page, url) -> Optional[RawPostCreate]:
        """Extract post data from an individual Instagram post page."""
        try:
            caption = ""
            meta_desc = await page.query_selector('meta[property="og:description"]')
            if meta_desc:
                caption = await meta_desc.get_attribute("content") or ""

            likes_el = await page.query_selector(
                'section span[class*="Like"] span, button[class*="like"] span'
            )
            likes = 0
            if likes_el:
                likes_text = await likes_el.inner_text()
                likes = self._parse_count(likes_text)

            shortcode = (
                url.split("/p/")[-1].split("/")[0]
                if "/p/" in url
                else url.split("/reel/")[-1].split("/")[0]
            )

            return RawPostCreate(
                post_id=shortcode,
                platform="instagram",
                account_id="",
                url=url,
                format="reel" if "/reel/" in url else "static_image",
                caption=caption,
                metrics=PostMetrics(likes=likes),
                engagement_rate=0.0,
                scrape_method="crawlee_playwright",
            )
        except Exception:
            return None

    async def _scrape_tiktok_browser(self, page, url, max_posts, result):
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        video_links = set()
        scroll_attempts = 0
        while len(video_links) < max_posts and scroll_attempts < max_posts // 3 + 10:
            links = await page.query_selector_all('a[href*="/video/"]')
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    video_links.add(href)
            await page.evaluate("window.scrollBy(0, 1200)")
            await asyncio.sleep(self._random_delay())
            scroll_attempts += 1

        for link in list(video_links)[:max_posts]:
            try:
                full_url = f"https://www.tiktok.com{link}" if link.startswith("/") else link
                video_id = link.split("/video/")[-1].split("?")[0] if "/video/" in link else ""
                result.add_post(
                    RawPostCreate(
                        post_id=video_id,
                        platform="tiktok",
                        account_id="",
                        url=full_url,
                        format="tiktok_video",
                        scrape_method="crawlee_playwright",
                    )
                )
            except Exception as e:
                result.add_error(f"TikTok extract error: {e}")

    async def _scrape_yt_browser(self, page, url, max_posts, result):
        videos_url = url.rstrip("/") + "/videos"
        await page.goto(videos_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        video_links = set()
        scroll_attempts = 0
        while len(video_links) < max_posts and scroll_attempts < max_posts // 4 + 10:
            links = await page.query_selector_all('a#video-title-link, a[href*="/watch?v="]')
            for link in links:
                href = await link.get_attribute("href")
                title = await link.get_attribute("title") or await link.inner_text()
                if href:
                    video_links.add((href, title.strip() if title else ""))
            await page.evaluate("window.scrollBy(0, 1000)")
            await asyncio.sleep(self._random_delay())
            scroll_attempts += 1

        for href, title in list(video_links)[:max_posts]:
            vid_id = href.split("v=")[-1].split("&")[0] if "v=" in href else ""
            full_url = f"https://www.youtube.com{href}" if href.startswith("/") else href
            result.add_post(
                RawPostCreate(
                    post_id=vid_id,
                    platform="youtube",
                    account_id="",
                    url=full_url,
                    format="youtube_video",
                    title=title,
                    caption=title,
                    scrape_method="crawlee_playwright",
                )
            )

    async def _scrape_tw_browser(self, page, url, max_posts, result):
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        tweet_links = set()
        scroll_attempts = 0
        while len(tweet_links) < max_posts and scroll_attempts < max_posts // 3 + 10:
            links = await page.query_selector_all('a[href*="/status/"]')
            for link in links:
                href = await link.get_attribute("href")
                if href and "/status/" in href:
                    tweet_links.add(href)
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(self._random_delay())
            scroll_attempts += 1

        for link in list(tweet_links)[:max_posts]:
            tid = link.split("/status/")[-1].split("?")[0] if "/status/" in link else ""
            full_url = f"https://x.com{link}" if link.startswith("/") else link
            result.add_post(
                RawPostCreate(
                    post_id=tid,
                    platform="twitter",
                    account_id="",
                    url=full_url,
                    format="tweet",
                    scrape_method="crawlee_playwright",
                )
            )

    async def _scrape_linkedin_browser(self, page, url, max_posts, result):
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        direct_candidates = await self._collect_social_link_candidates(
            page,
            link_patterns=["/posts/", "/feed/update/", "/pulse/"],
            max_candidates=max_posts * 3,
        )
        posts = self._linkedin_posts_from_candidates(direct_candidates, max_posts, url)

        if len(posts) < max_posts:
            search_candidates = await self._scrape_search_result_posts(
                page,
                query=self._build_social_search_query("linkedin", url),
                link_patterns=["linkedin.com/posts/", "linkedin.com/feed/update/", "linkedin.com/pulse/"],
                max_candidates=max_posts * 3,
            )
            posts.extend(
                self._linkedin_posts_from_candidates(
                    search_candidates,
                    max_posts - len(posts),
                    url,
                    seen_urls={post.url for post in posts},
                )
            )

        if not posts:
            result.add_error(
                "LinkedIn returned no public post links; the profile is likely behind LinkedIn authwall"
            )
            return

        for post in posts[:max_posts]:
            result.add_post(post)

        if len(posts) < max_posts:
            result.add_error(
                f"LinkedIn public scraping found only {len(posts)} accessible posts for {url}"
            )

    async def _scrape_fb_browser(self, page, url, max_posts, result):
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        direct_candidates = await self._collect_social_link_candidates(
            page,
            link_patterns=["/posts/", "/reel/", "/videos/", "story_fbid=", "fbid="],
            max_candidates=max_posts * 3,
        )
        posts = self._facebook_posts_from_candidates(direct_candidates, max_posts, url)

        if len(posts) < max_posts:
            search_candidates = await self._scrape_search_result_posts(
                page,
                query=self._build_social_search_query("facebook", url),
                link_patterns=["facebook.com/", "fb.watch/"],
                max_candidates=max_posts * 3,
            )
            posts.extend(
                self._facebook_posts_from_candidates(
                    search_candidates,
                    max_posts - len(posts),
                    url,
                    seen_urls={post.url for post in posts},
                )
            )

        if not posts:
            result.add_error(
                "Facebook returned no public post links; page visibility or anti-bot defenses blocked extraction"
            )
            return

        for post in posts[:max_posts]:
            result.add_post(post)

        if len(posts) < max_posts:
            result.add_error(
                f"Facebook public scraping found only {len(posts)} accessible posts for {url}"
            )

    async def _collect_social_link_candidates(
        self,
        page,
        link_patterns: List[str],
        max_candidates: int,
    ) -> List[Dict[str, str]]:
        raw_candidates = await page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]')).map((anchor) => {
                const href = anchor.getAttribute('href') || '';
                const text = (anchor.innerText || anchor.textContent || '').trim();
                const title = (anchor.getAttribute('title') || anchor.getAttribute('aria-label') || '').trim();
                return { href, text, title };
            })
            """
        )

        candidates: List[Dict[str, str]] = []
        seen_urls = set()
        base_url = page.url

        for item in raw_candidates:
            href = self._normalize_candidate_url(base_url, item.get("href", ""))
            if not href:
                continue
            lowered = href.lower()
            if not any(pattern.lower() in lowered for pattern in link_patterns):
                continue
            if href in seen_urls:
                continue
            seen_urls.add(href)
            candidates.append(
                {
                    "href": href,
                    "text": self._clean_candidate_text(item.get("text", "")),
                    "title": self._clean_candidate_text(item.get("title", "")),
                }
            )
            if len(candidates) >= max_candidates:
                break

        return candidates

    async def _scrape_search_result_posts(
        self,
        page,
        query: str,
        link_patterns: List[str],
        max_candidates: int,
    ) -> List[Dict[str, str]]:
        search_url = f"https://www.bing.com/search?q={quote(query)}"
        await page.goto(search_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        return await self._collect_social_link_candidates(page, link_patterns, max_candidates)

    def _linkedin_posts_from_candidates(
        self,
        candidates: List[Dict[str, str]],
        max_posts: int,
        account_url: str,
        seen_urls: Optional[set[str]] = None,
    ) -> List[RawPostCreate]:
        posts: List[RawPostCreate] = []
        dedupe_urls = seen_urls or set()
        account_handle = self._extract_account_handle(account_url)

        for candidate in candidates:
            href = candidate.get("href", "")
            if href in dedupe_urls:
                continue
            post_id = self._extract_post_id_from_url(href, "linkedin")
            if not post_id:
                continue
            caption = self._clean_candidate_text(candidate.get("text") or candidate.get("title") or "")
            post = RawPostCreate(
                post_id=post_id,
                platform="linkedin",
                account_id=account_handle,
                url=href,
                format="linkedin_post",
                caption=caption,
                title=self._derive_title(caption, "LinkedIn post"),
                metrics=PostMetrics(),
                engagement_rate=0.0,
                scrape_method="crawlee_playwright",
                raw_json=json.dumps(candidate, default=str)[:2000],
            )
            posts.append(post)
            dedupe_urls.add(href)
            if len(posts) >= max_posts:
                break

        return posts

    def _facebook_posts_from_candidates(
        self,
        candidates: List[Dict[str, str]],
        max_posts: int,
        account_url: str,
        seen_urls: Optional[set[str]] = None,
    ) -> List[RawPostCreate]:
        posts: List[RawPostCreate] = []
        dedupe_urls = seen_urls or set()
        account_handle = self._extract_account_handle(account_url)

        for candidate in candidates:
            href = candidate.get("href", "")
            if href in dedupe_urls:
                continue
            post_id = self._extract_post_id_from_url(href, "facebook")
            if not post_id:
                continue

            lowered = href.lower()
            if "/reel/" in lowered:
                fmt = "facebook_reel"
            elif "/videos/" in lowered or "fb.watch/" in lowered:
                fmt = "facebook_video"
            else:
                fmt = "facebook_post"

            caption = self._clean_candidate_text(candidate.get("text") or candidate.get("title") or "")
            post = RawPostCreate(
                post_id=post_id,
                platform="facebook",
                account_id=account_handle,
                url=href,
                format=fmt,
                caption=caption,
                title=self._derive_title(caption, "Facebook post"),
                metrics=PostMetrics(),
                engagement_rate=0.0,
                scrape_method="crawlee_playwright",
                raw_json=json.dumps(candidate, default=str)[:2000],
            )
            posts.append(post)
            dedupe_urls.add(href)
            if len(posts) >= max_posts:
                break

        return posts

    def _build_social_search_query(self, platform: str, account_url: str) -> str:
        account_handle = self._extract_account_handle(account_url)
        if platform == "linkedin":
            return f'site:linkedin.com/posts "{account_handle}" OR "{account_url}"'
        if platform == "facebook":
            return f'site:facebook.com "{account_handle}" ("posts" OR "reel" OR "videos")'
        return account_url

    def _normalize_candidate_url(self, base_url: str, href: str) -> str:
        href = (href or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            return ""

        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            return ""

        path = parsed.path.rstrip("/")
        if not path:
            path = "/"

        query = parsed.query
        if query:
            if "facebook.com" in parsed.netloc or "fb.watch" in parsed.netloc:
                params = parse_qs(query)
                kept = []
                for key in ("story_fbid", "fbid"):
                    if params.get(key):
                        kept.append(f"{key}={params[key][0]}")
                query = "&".join(kept)
            else:
                query = ""

        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if query:
            normalized = f"{normalized}?{query}"
        return normalized

    def _extract_account_handle(self, account_url: str) -> str:
        parsed = urlparse(account_url)
        parts = [part for part in parsed.path.split("/") if part]
        ignored = {"in", "company", "public", "user", "users", "pages"}
        for part in reversed(parts):
            if part not in ignored:
                return part.lstrip("@")
        return parsed.netloc

    def _extract_post_id_from_url(self, url: str, platform: str) -> str:
        parsed = urlparse(url)
        path = parsed.path

        if platform == "linkedin":
            match = re.search(r"/posts/([^/?#]+)", path)
            if match:
                return match.group(1)
            activity = re.search(r"activity[:/-](\d+)", path)
            if activity:
                return activity.group(1)
            pulse = re.search(r"/pulse/([^/?#]+)", path)
            if pulse:
                return pulse.group(1)
            return ""

        if platform == "facebook":
            for pattern in (r"/posts/([^/?#]+)", r"/reel/([^/?#]+)", r"/videos/([^/?#]+)"):
                match = re.search(pattern, path)
                if match:
                    return match.group(1)

            if "fb.watch" in parsed.netloc:
                slug = path.strip("/")
                return slug.split("/")[0] if slug else ""

            params = parse_qs(parsed.query)
            for key in ("story_fbid", "fbid"):
                values = params.get(key)
                if values:
                    return values[0]
            return ""

        return ""

    def _clean_candidate_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "")).strip()
        if cleaned.lower() in {"like", "comment", "share", "follow", "reply", "view more"}:
            return ""
        return cleaned[:500]

    def _derive_title(self, text: str, fallback: str) -> str:
        text = (text or "").strip()
        if not text:
            return fallback
        sentence = re.split(r"[.!?]\s+", text, maxsplit=1)[0].strip()
        return sentence[:120] or fallback

    def _random_delay(self) -> float:
        import random

        return random.uniform(self._delay_min, self._delay_max)

    @staticmethod
    def _parse_count(text: str) -> int:
        """Parse human-readable counts like '1.2K', '3.4M'."""
        text = text.strip().replace(",", "").upper()
        try:
            if text.endswith("K"):
                return int(float(text[:-1]) * 1000)
            if text.endswith("M"):
                return int(float(text[:-1]) * 1000000)
            if text.endswith("B"):
                return int(float(text[:-1]) * 1000000000)
            return int(text)
        except (ValueError, TypeError):
            return 0
