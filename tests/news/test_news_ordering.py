from __future__ import annotations

from dashboard.pages.news_page import _dedupe_items


def test_news_items_are_deduped_and_sorted_newest_first() -> None:
    feed_data = {
        "rates": {
            "items": [
                {
                    "title": "Older rates headline",
                    "bucket": "rates",
                    "published_at": "2026-04-28T10:00:00+00:00",
                },
                {
                    "title": "Duplicate headline",
                    "bucket": "rates",
                    "published_at": "2026-04-28T09:00:00+00:00",
                },
            ]
        },
        "macro": {
            "items": [
                {
                    "title": "Newest macro headline",
                    "bucket": "macro",
                    "published_at": "2026-04-29T12:00:00+00:00",
                },
                {
                    "title": "Duplicate headline",
                    "bucket": "macro",
                    "published_at": "2026-04-29T11:00:00+00:00",
                },
                {
                    "title": "Undated headline",
                    "bucket": "macro",
                    "published_at": None,
                },
            ]
        },
    }

    items = _dedupe_items(feed_data)

    assert [item["title"] for item in items] == [
        "Newest macro headline",
        "Duplicate headline",
        "Older rates headline",
        "Undated headline",
    ]
    assert items[1]["bucket"] == "macro"
