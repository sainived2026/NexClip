"""
Nexearch — Base Scraper Interface
Abstract interface for all scraping backends.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from nexearch.schemas.raw_post import RawPostCreate


class ScrapingResult:
    """Result container for a scraping operation."""
    def __init__(self):
        self.posts: List[RawPostCreate] = []
        self.total_scraped: int = 0
        self.resume_cursor: str = ""
        self.had_errors: bool = False
        self.error_messages: List[str] = []
        self.was_blocked: bool = False
        self.blocked_reason: str = ""
        self.duration_seconds: float = 0.0
        self.scrape_method: str = ""

    def add_post(self, post: RawPostCreate):
        self.posts.append(post)
        self.total_scraped = len(self.posts)

    def add_error(self, msg: str):
        self.error_messages.append(msg)
        self.had_errors = True


class BaseScraper(ABC):
    """
    Abstract scraper interface.
    All scraping backends (Apify, Platform API, Crawlee+Playwright) implement this.
    """

    def __init__(self, platform: str, client_id: str):
        self.platform = platform
        self.client_id = client_id
        self.logger = logger.bind(scraper=self.__class__.__name__, platform=platform)

    @abstractmethod
    async def scrape(
        self,
        account_url: str,
        max_posts: int = 100,
        resume_cursor: Optional[str] = None,
        credentials: Optional[Dict[str, Any]] = None,
        since_date: Optional[datetime] = None,
    ) -> ScrapingResult:
        """
        Scrape posts from the given account URL.

        Args:
            account_url: Full URL of the social media account
            max_posts: Maximum number of posts to scrape
            resume_cursor: Resume from this cursor (for resumable scraping)
            credentials: Optional auth credentials (cookies, tokens, etc.)
            since_date: Only scrape posts newer than this date

        Returns:
            ScrapingResult with list of RawPostCreate objects
        """
        pass

    @abstractmethod
    async def refresh_metrics(
        self,
        account_url: str,
        post_ids: List[str],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Refresh engagement metrics for existing posts.
        Returns dict mapping post_id -> updated metrics dict.
        """
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if this scraping backend is available and configured."""
        pass

    @property
    @abstractmethod
    def scrape_method_name(self) -> str:
        """Return the name of the scraping method."""
        pass

    def _compute_engagement_rate(
        self,
        likes: int = 0,
        comments: int = 0,
        shares: Optional[int] = None,
        saves: Optional[int] = None,
        views: Optional[int] = None,
        followers: Optional[int] = None,
    ) -> float:
        """Compute engagement rate from available metrics."""
        total_engagement = likes + comments
        if shares:
            total_engagement += shares
        if saves:
            total_engagement += saves

        if views and views > 0:
            return round(total_engagement / views, 6)
        elif followers and followers > 0:
            return round(total_engagement / followers, 6)
        return 0.0

    def _extract_day_hour(self, posted_at: Optional[datetime]):
        """Extract day_of_week and hour_of_day from a datetime."""
        if not posted_at:
            return None, None
        return posted_at.strftime("%A"), posted_at.hour
