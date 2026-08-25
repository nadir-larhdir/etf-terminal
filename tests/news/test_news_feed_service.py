from __future__ import annotations

import pytest

from services.news.news_feed_service import NewsFeedService

FEEDS = {"rates": {"label": "Rates", "url": "https://feed.test/rates"}}


def _rss(*items: str) -> bytes:
    body = "".join(items)
    return f"<rss><channel>{body}</channel></rss>".encode()


def _item(
    title: str,
    link: str = "https://news.test/a",
    *,
    pub_date: str | None = None,
    source: str = "",
) -> str:
    parts = [f"<title>{title}</title>", f"<link>{link}</link>"]
    if pub_date:
        parts.append(f"<pubDate>{pub_date}</pubDate>")
    if source:
        parts.append(f"<source>{source}</source>")
    return f"<item>{''.join(parts)}</item>"


class _Response:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _Session:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls: list[tuple[str, int]] = []

    def get(self, url: str, timeout: int):
        self.calls.append((url, timeout))
        return _Response(self.content)


def _service(content: bytes) -> NewsFeedService:
    return NewsFeedService(feeds=FEEDS, session=_Session(content))  # type: ignore[arg-type]


def test_a_relevant_headline_is_normalised_into_an_item() -> None:
    service = _service(_rss(_item("Treasury yields climb as Fed holds")))

    items = service.fetch_feed("rates")

    assert len(items) == 1
    assert items[0]["title"] == "Treasury yields climb as Fed holds"
    assert items[0]["link"] == "https://news.test/a"
    assert items[0]["bucket"]


def test_an_item_without_a_title_or_link_is_dropped() -> None:
    service = _service(_rss("<item><title>Treasury yields climb</title></item>"))

    assert service.fetch_feed("rates") == []


def test_a_headline_that_does_not_match_the_feed_is_dropped() -> None:
    service = _service(_rss(_item("Celebrity chef opens new restaurant")))

    assert service.fetch_feed("rates") == []


def test_a_missing_source_falls_back_to_a_generic_label() -> None:
    service = _service(_rss(_item("Treasury yields climb as Fed holds")))

    assert service.fetch_feed("rates")[0]["source"] == "News Feed"


def test_a_supplied_source_is_preserved() -> None:
    service = _service(_rss(_item("Treasury yields climb", source="Reuters")))

    assert service.fetch_feed("rates")[0]["source"] == "Reuters"


def test_items_are_returned_newest_first() -> None:
    service = _service(
        _rss(
            _item("Treasury yields climb older", pub_date="Mon, 18 Aug 2026 10:00:00 +0000"),
            _item("Treasury yields climb newer", pub_date="Thu, 21 Aug 2026 10:00:00 +0000"),
        )
    )

    titles = [item["title"] for item in service.fetch_feed("rates")]

    assert titles == ["Treasury yields climb newer", "Treasury yields climb older"]


def test_undated_items_sort_last() -> None:
    service = _service(
        _rss(
            _item("Treasury yields climb undated"),
            _item("Treasury yields climb dated", pub_date="Thu, 21 Aug 2026 10:00:00 +0000"),
        )
    )

    titles = [item["title"] for item in service.fetch_feed("rates")]

    assert titles[-1] == "Treasury yields climb undated"


def test_an_unparseable_publication_date_is_stored_as_none() -> None:
    service = _service(_rss(_item("Treasury yields climb", pub_date="not-a-date")))

    assert service.fetch_feed("rates")[0]["published_at"] is None


def test_the_limit_caps_how_many_items_are_returned() -> None:
    service = _service(_rss(*[_item(f"Treasury yields climb {i}") for i in range(20)]))

    assert len(service.fetch_feed("rates", limit=3)) == 3


def test_the_request_carries_a_timeout() -> None:
    service = _service(_rss(_item("Treasury yields climb")))

    service.fetch_feed("rates")

    assert service.session.calls[0][1] > 0  # type: ignore[attr-defined]


def test_fetch_all_returns_a_labelled_entry_per_configured_feed() -> None:
    service = _service(_rss(_item("Treasury yields climb as Fed holds")))

    result = service.fetch_all(limit_per_feed=2)

    assert set(result) == {"rates"}
    assert result["rates"]["label"] == "Rates"
    assert len(result["rates"]["items"]) == 1


def test_fetch_all_with_no_configured_feeds_returns_nothing() -> None:
    service = NewsFeedService(feeds={}, session=_Session(b""))  # type: ignore[arg-type]

    assert service.fetch_all() == {}


@pytest.mark.parametrize("raw", [None, "", "garbage", "Mon, 32 Zzz 2026"])
def test_bad_publication_dates_never_raise(raw: str | None) -> None:
    assert NewsFeedService(feeds=FEEDS)._parse_pub_date(raw) is None


def test_a_naive_timestamp_is_treated_as_utc_for_ordering() -> None:
    service = NewsFeedService(feeds=FEEDS)

    naive = service._published_timestamp({"published_at": "2026-08-21T10:00:00"})
    aware = service._published_timestamp({"published_at": "2026-08-21T10:00:00+00:00"})

    assert naive == aware


def test_an_unsortable_timestamp_sorts_last() -> None:
    service = NewsFeedService(feeds=FEEDS)

    assert service._published_timestamp({"published_at": "nonsense"}) == float("-inf")
