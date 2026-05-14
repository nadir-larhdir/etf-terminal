from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from dashboard.pages.news_page import _dedupe_items, _normalise_upcoming_events


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


def test_upcoming_events_are_dynamic_us_macro_events_only() -> None:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    rows = [
        {
            "date": "2026-05-07 08:30:00",
            "event": "Initial Jobless Claims",
            "country": "US",
            "currency": "USD",
            "importance": "high",
        },
        {
            "date": "2026-05-07 10:00:00",
            "event": "ISM Services PMI",
            "country": "US",
            "currency": "USD",
            "importance": "medium",
        },
        {
            "date": "2026-05-08 08:30:00",
            "event": "Nonfarm Payrolls",
            "country": "United States",
            "currency": "USD",
            "importance": "high",
        },
        {
            "date": "2026-05-08 09:00:00",
            "event": "French Industrial Production",
            "country": "France",
            "currency": "EUR",
            "importance": "high",
        },
    ]

    events = _normalise_upcoming_events(rows, now=now)

    assert [event["name"] for event in events] == ["ISM Services PMI", "Nonfarm Payrolls"]
    assert events[0]["time"] == "10:00 ET"
    assert events[0]["day"] == "Today"
    assert events[1]["day"] == "Tomorrow"


def test_upcoming_events_can_fallback_to_next_us_event() -> None:
    now = datetime(2026, 5, 7, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    rows = [
        {
            "date": "2026-05-07 11:00:00",
            "event": "Consumer Credit Change",
            "country": "US",
            "currency": "USD",
            "impact": "Low",
        },
        {
            "date": "2026-05-07 12:00:00",
            "event": "German Bond Auction",
            "country": "DE",
            "currency": "EUR",
            "impact": "High",
        },
    ]

    assert _normalise_upcoming_events(rows, now=now) == []

    events = _normalise_upcoming_events(rows, now=now, require_relevance=False)

    assert [event["name"] for event in events] == ["Consumer Credit Change"]
