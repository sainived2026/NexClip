"""
Nexearch — Scraper Factory
Creates the appropriate scraper backend based on client configuration.
"""

from typing import Optional, Dict, Any
from loguru import logger

from nexearch.tools.scrapers.base import BaseScraper
from nexearch.tools.scrapers.apify_scraper import ApifyScraper
from nexearch.tools.scrapers.platform_api_scraper import PlatformAPIScraper
from nexearch.tools.scrapers.crawlee_scraper import CrawleePlaywrightScraper


def create_scraper(
    method: str,
    platform: str,
    client_id: str,
    access_token: str = "",
    page_id: str = "",
    api_key: str = "",
    buffer_api_key: str = "",
    metricool_api_key: str = "",
    metricool_user_id: str = "",
    metricool_blog_id: str = "",
) -> BaseScraper:
    """
    Factory function to create the appropriate scraper.

    Args:
        method: "apify", "platform_api", "crawlee_playwright", "buffer", or "metricool"
        platform: "instagram", "tiktok", "youtube", "twitter", "linkedin", "facebook", "threads"
        client_id: Nexearch client ID
        access_token: Platform access token (for platform_api method)
        page_id: Platform page/profile ID (for platform_api method)
        api_key: API key (for platform_api method, e.g. YouTube)
        buffer_api_key: Buffer API key (buffer falls back to Crawlee)
        metricool_api_key: Metricool API key (uses native Metricool REST API — no browser needed)
        metricool_user_id: Metricool userId (auto-resolved from API if missing)
        metricool_blog_id: Metricool blogId / brandId (auto-resolved from API if missing)

    Returns:
        Configured BaseScraper instance
    """
    if method == "apify":
        return ApifyScraper(platform=platform, client_id=client_id)

    elif method == "platform_api":
        return PlatformAPIScraper(
            platform=platform, client_id=client_id,
            access_token=access_token, page_id=page_id, api_key=api_key,
        )

    elif method == "crawlee_playwright":
        return CrawleePlaywrightScraper(platform=platform, client_id=client_id)

    elif method == "metricool":
        # ── Metricool: use the native REST API directly — no browser needed ──
        from nexearch.tools.scrapers.metricool_scraper import MetricoolScraper
        logger.info(
            f"[ScraperFactory] metricool → MetricoolScraper (direct API) for {platform} "
            f"(client: {client_id})"
        )
        return MetricoolScraper(
            platform=platform,
            client_id=client_id,
            api_token=metricool_api_key,
            user_id=metricool_user_id,
            blog_id=metricool_blog_id,
        )

    elif method == "buffer":
        # Buffer doesn't have a content analytics API — use Crawlee to scrape the platform URL
        logger.info(f"[ScraperFactory] buffer → CrawleePlaywrightScraper for {platform}")
        return CrawleePlaywrightScraper(platform=platform, client_id=client_id)

    else:
        logger.warning(f"[ScraperFactory] Unknown scraping method '{method}', defaulting to Apify")
        return ApifyScraper(platform=platform, client_id=client_id)


async def get_best_available_scraper(
    platform: str,
    client_id: str,
    preferred_method: str = "apify",
    **kwargs,
) -> BaseScraper:
    """
    Get the best available scraper, falling back through methods.
    Priority: metricool (if key present) → preferred_method → apify → platform_api → crawlee_playwright

    When a metricool_api_key is present it is always tried first since it
    requires no browser and returns richer analytics data directly from the API.

    Args:
        platform: Target platform
        client_id: Nexearch client ID
        preferred_method: Preferred scraping method
        **kwargs: Additional args (access_token, page_id, api_key, metricool_api_key, …)
    """
    methods: list = []

    # Always prefer Metricool if a key is present — it's the richest data source
    if kwargs.get("metricool_api_key"):
        methods.append("metricool")

    methods.append(preferred_method)

    for m in ["apify", "platform_api", "crawlee_playwright"]:
        if m not in methods:
            methods.append(m)

    for method in methods:
        scraper = create_scraper(method, platform, client_id, **kwargs)
        if await scraper.check_availability():
            logger.info(
                f"[ScraperFactory] Using '{method}' scraper for {platform} (client: {client_id})"
            )
            return scraper

    logger.warning(f"[ScraperFactory] No scraper available for {platform}, returning Apify (may fail)")
    return ApifyScraper(platform=platform, client_id=client_id)
