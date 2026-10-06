"""Base scraper interface."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
import httpx

from ..models import ContentItem


def short_error(exc: Exception) -> str:
    """First line of an exception, e.g. "HTTPStatusError: Client error '404 Not Found'"."""
    message = str(exc).splitlines()[0] if str(exc) else ""
    return f"{type(exc).__name__}: {message}".rstrip(": ")


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    def __init__(self, config: dict, http_client: httpx.AsyncClient):
        """Initialize scraper.

        Args:
            config: Scraper-specific configuration
            http_client: Shared async HTTP client
        """
        self.config = config
        self.client = http_client
        # Per-sub-source errors ({source key: message}) for sources a scraper
        # skips instead of failing the whole fetch; see src/source_health.py.
        self.source_errors: dict[str, str] = {}

    @abstractmethod
    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch content items published since the given time.

        Args:
            since: Only fetch items published after this time

        Returns:
            List[ContentItem]: Fetched content items
        """
        pass

    def _generate_id(self, source_type: str, subtype: str, native_id: str) -> str:
        """Generate unique content item ID.

        Args:
            source_type: Source type (github, hackernews, etc.)
            subtype: Content subtype (event, release, story, etc.)
            native_id: Native ID from the source platform

        Returns:
            str: Unique ID in format {source}:{subtype}:{native_id}
        """
        return f"{source_type}:{subtype}:{native_id}"
