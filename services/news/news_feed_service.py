from __future__ import annotations

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import requests

from config import NEWS_FEEDS


class NewsFeedService:
    """Fetch and normalize RSS headlines for the News tab."""

    def __init__(self, feeds: dict | None = None):
        self.feeds = feeds or NEWS_FEEDS

    def fetch_all(self, limit_per_feed: int = 5) -> dict[str, dict]:
        return {
            feed_key: {
                "label": feed_config["label"],
                "items": self.fetch_feed(feed_key, limit=limit_per_feed),
            }
            for feed_key, feed_config in self.feeds.items()
        }

    def fetch_feed(self, feed_key: str, limit: int = 5) -> list[dict]:
        feed_config = self.feeds[feed_key]
        response = requests.get(feed_config["url"], timeout=20)
        response.raise_for_status()

        root = ElementTree.fromstring(response.content)
        items: list[dict] = []
        for item in root.findall("./channel/item")[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            source = (item.findtext("source") or "").strip()
            pub_date = self._parse_pub_date(item.findtext("pubDate"))

            if not title or not link:
                continue

            items.append(
                {
                    "title": title,
                    "link": link,
                    "source": source or "News Feed",
                    "published_at": pub_date.isoformat() if pub_date is not None else None,
                }
            )

        return items

    def _parse_pub_date(self, pub_date: str | None):
        if not pub_date:
            return None
        try:
            return parsedate_to_datetime(pub_date)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
