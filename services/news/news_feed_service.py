"""RSS feed fetching and filtering for the News tab."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

from config import NEWS_FEEDS


class NewsFeedService:
    """Fetch, filter, and normalise RSS headlines for the News tab.

    Applies promotional-content filtering and bucket keyword matching so only
    relevant fixed-income headlines reach the dashboard.
    """

    PROMOTIONAL_PATTERNS = (
        "which is the better",
        "which is better",
        "the best ones",
        "best ",
        "top ",
        "should you buy",
        "buy now",
        "investors are flocking",
        "why this etf",
        "why this stock",
        "motley fool",
    )

    BUCKET_KEYWORDS = {
        "rates": (
            "treasury",
            "yield",
            "yields",
            "curve",
            "bond market",
            "duration",
            "auction",
            "rates",
            "fed",
            "fomc",
        ),
        "credit": (
            "credit",
            "spread",
            "spreads",
            "investment grade",
            "high yield",
            "junk bond",
            "corporate bond",
            "bond etf",
            "etf",
            "fund flow",
            "lqd",
            "hyg",
            "jnk",
            "vcit",
            "igtb",
            "igsb",
            "istb",
        ),
        "macro": (
            "inflation",
            "cpi",
            "pce",
            "payroll",
            "unemployment",
            "labor",
            "gdp",
            "economy",
            "economic",
            "fed",
            "rates",
            "treasury",
            "macro",
        ),
    }

    def __init__(self, feeds: dict | None = None):
        self.feeds = feeds or NEWS_FEEDS

    def fetch_all(self, limit_per_feed: int = 5) -> dict[str, dict]:
        """Fetch all configured feeds and return a keyed dict of label + items."""
        return {
            feed_key: {
                "label": feed_config["label"],
                "items": self.fetch_feed(feed_key, limit=limit_per_feed),
            }
            for feed_key, feed_config in self.feeds.items()
        }

    def fetch_feed(self, feed_key: str, limit: int = 5) -> list[dict]:
        """Fetch a single RSS feed and return up to limit filtered headline dicts."""
        feed_config = self.feeds[feed_key]
        response = requests.get(feed_config["url"], timeout=20)
        response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        items: list[dict] = []
        raw_limit = max(limit * 4, 12)
        for item in root.findall("./channel/item")[:raw_limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source = (item.findtext("source") or "").strip()
            pub_date = self._parse_pub_date(item.findtext("pubDate"))

            if not title or not link:
                continue
            if not self._is_relevant_headline(feed_key, title, source):
                continue

            items.append(
                {
                    "title": title,
                    "link": link,
                    "source": source or "News Feed",
                    "published_at": pub_date.isoformat() if pub_date is not None else None,
                }
            )
            if len(items) >= limit:
                break

        return items

    def _is_relevant_headline(self, feed_key: str, title: str, source: str) -> bool:
        """Return True when a headline passes promotional filtering and matches bucket keywords."""
        title_lower = title.lower()
        source_lower = source.lower()
        combined = f"{title_lower} {source_lower}"

        if any(pattern in combined for pattern in self.PROMOTIONAL_PATTERNS):
            return False
        if "motley fool" in source_lower and "etf" in title_lower:
            return False

        keywords = self.BUCKET_KEYWORDS.get(feed_key, ())
        return any(keyword in title_lower for keyword in keywords)

    def _parse_pub_date(self, pub_date: str | None):
        """Parse an RFC-2822 pubDate string into a datetime, returning None on failure."""
        if not pub_date:
            return None
        try:
            return parsedate_to_datetime(pub_date)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
