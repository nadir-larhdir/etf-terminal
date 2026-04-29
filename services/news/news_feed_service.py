"""RSS feed fetching and filtering for the News tab."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

from config import NEWS_FEEDS
from services.news.taxonomy import classify_bucket, is_promotional, matches_feed


class NewsFeedService:
    """Fetch, filter, and normalise RSS headlines for the News tab.

    Applies promotional-content filtering and bucket keyword matching so only
    relevant fixed-income headlines reach the dashboard.
    """

    def __init__(self, feeds: dict | None = None, session: requests.Session | None = None):
        self.feeds = feeds or NEWS_FEEDS
        self.session = session or requests.Session()

    def fetch_all(self, limit_per_feed: int = 5) -> dict[str, dict]:
        """Fetch all configured feeds concurrently and return label + items by feed key."""
        result = {
            feed_key: {"label": feed_config["label"], "items": []}
            for feed_key, feed_config in self.feeds.items()
        }
        if not result:
            return result

        max_workers = min(4, len(result))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.fetch_feed, feed_key, limit_per_feed): feed_key
                for feed_key in result
            }
            for future in as_completed(futures):
                result[futures[future]]["items"] = future.result()
        return result

    def fetch_feed(self, feed_key: str, limit: int = 5) -> list[dict]:
        """Fetch a single RSS feed and return up to limit filtered headline dicts."""
        feed_config = self.feeds[feed_key]
        response = self.session.get(feed_config["url"], timeout=20)
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
                    "bucket": classify_bucket(title),
                    "published_at": pub_date.isoformat() if pub_date is not None else None,
                }
            )

        return sorted(items, key=self._published_timestamp, reverse=True)[:limit]

    def _is_relevant_headline(self, feed_key: str, title: str, source: str) -> bool:
        """Return True when a headline passes promotional filtering and matches bucket keywords."""
        return not is_promotional(title, source) and matches_feed(feed_key, title)

    def _parse_pub_date(self, pub_date: str | None):
        """Parse an RFC-2822 pubDate string into a datetime, returning None on failure."""
        if not pub_date:
            return None
        try:
            return parsedate_to_datetime(pub_date)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None

    def _published_timestamp(self, item: dict) -> float:
        """Return a sortable timestamp for a news item, with undated items last."""
        published_at = item.get("published_at")
        if not published_at:
            return float("-inf")
        try:
            dt = datetime.fromisoformat(str(published_at))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.timestamp()
        except (TypeError, ValueError, OSError):
            return float("-inf")
