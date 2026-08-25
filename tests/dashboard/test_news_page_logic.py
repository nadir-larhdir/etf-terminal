"""The pure logic behind the News page: dedupe, ordering, calendar filtering, sentiment."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from dashboard.pages.news_page import (
    _compute_sentiment,
    _compute_summary_counts,
    _dedupe_items,
    _event_day_label,
    _is_relevant_event,
    _is_us_event,
    _mini_sparkline_svg,
    _normalise_upcoming_events,
    _published_timestamp,
    _relative_time,
)

NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def _feed(*items: dict[str, object]) -> dict[str, dict[str, object]]:
    return {"rates": {"label": "Rates", "items": list(items)}}


def _item(title: str, *, published_at: str | None = None, bucket: str = "rates") -> dict:
    return {
        "title": title,
        "link": "https://a.test",
        "bucket": bucket,
        "published_at": published_at,
    }


# ── relative time ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("minutes_ago", "expected"),
    [(0, "just now"), (5, "5m ago"), (59, "59m ago"), (60, "1h ago"), (23 * 60, "23h ago")],
)
def test_recent_timestamps_read_in_minutes_then_hours(minutes_ago: int, expected: str) -> None:
    stamp = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat()

    assert _relative_time(stamp) == expected


def test_older_timestamps_read_in_days() -> None:
    stamp = (datetime.now(UTC) - timedelta(days=3)).isoformat()

    assert _relative_time(stamp) == "3d ago"


@pytest.mark.parametrize("raw", [None, "", "not-a-date"])
def test_an_unusable_timestamp_renders_as_nothing(raw: str | None) -> None:
    assert _relative_time(raw) == ""


def test_a_naive_timestamp_is_read_as_utc() -> None:
    stamp = (datetime.now(UTC) - timedelta(minutes=5)).replace(tzinfo=None).isoformat()

    assert _relative_time(stamp) == "5m ago"


# ── ordering and dedupe ─────────────────────────────────────────────────────


def test_undated_items_sort_last() -> None:
    assert _published_timestamp({"published_at": None}) == float("-inf")


def test_an_unparseable_timestamp_sorts_last() -> None:
    assert _published_timestamp({"published_at": "nonsense"}) == float("-inf")


def test_items_are_returned_newest_first() -> None:
    items = _dedupe_items(
        _feed(
            _item("Older headline", published_at="2026-08-18T10:00:00+00:00"),
            _item("Newer headline", published_at="2026-08-21T10:00:00+00:00"),
        )
    )

    assert [item["title"] for item in items] == ["Newer headline", "Older headline"]


def test_a_duplicate_headline_is_collapsed_to_its_newest_copy() -> None:
    items = _dedupe_items(
        _feed(
            _item("Same headline", published_at="2026-08-18T10:00:00+00:00"),
            _item("Same   headline", published_at="2026-08-21T10:00:00+00:00"),
        )
    )

    assert len(items) == 1
    assert items[0]["published_at"] == "2026-08-21T10:00:00+00:00"


def test_dedupe_is_case_and_whitespace_insensitive() -> None:
    items = _dedupe_items(_feed(_item("Fed Holds Rates"), _item("  fed holds rates  ")))

    assert len(items) == 1


def test_items_without_a_title_are_dropped() -> None:
    assert _dedupe_items(_feed(_item(""), _item("   "))) == []


def test_items_are_pooled_across_every_bucket() -> None:
    feed = {
        "rates": {"items": [_item("Rates headline")]},
        "credit": {"items": [_item("Credit headline")]},
        "macro": {"items": [_item("Macro headline")]},
        "etfs": {"items": [_item("ETF headline")]},
    }

    assert len(_dedupe_items(feed)) == 4


def test_an_empty_feed_yields_no_items() -> None:
    assert _dedupe_items({}) == []


def test_an_item_without_a_bucket_is_classified_from_its_title() -> None:
    items = _dedupe_items({"rates": {"items": [{"title": "Treasury yields rise", "bucket": None}]}})

    assert items[0]["bucket"]


# ── economic calendar ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "row",
    [
        {"country": "US"},
        {"country": "United States"},
        {"currency": "USD"},
        {"country": "usa"},
    ],
)
def test_us_rows_are_recognised(row: dict) -> None:
    assert _is_us_event(row) is True


@pytest.mark.parametrize("row", [{"country": "Germany"}, {"currency": "EUR"}, {}])
def test_non_us_rows_are_excluded(row: dict) -> None:
    assert _is_us_event(row) is False


def test_a_keyword_event_is_relevant_regardless_of_importance() -> None:
    assert _is_relevant_event({"event": "CPI m/m", "importance": "low"}) is True


def test_a_high_importance_event_is_relevant_without_a_keyword() -> None:
    assert _is_relevant_event({"event": "Widget Shipments", "importance": "high"}) is True


def test_an_unnamed_event_is_never_relevant() -> None:
    assert _is_relevant_event({"importance": "high"}) is False


def test_a_low_importance_unrelated_event_is_filtered_out() -> None:
    assert _is_relevant_event({"event": "Widget Shipments", "importance": "low"}) is False


@pytest.mark.parametrize(("days_ahead", "label"), [(0, "Today"), (1, "Tomorrow"), (5, "Aug 26")])
def test_event_days_are_labelled_relative_to_today(days_ahead: int, label: str) -> None:
    event = NOW + timedelta(days=days_ahead)

    assert _event_day_label(event, NOW.date()) == label


def test_past_events_are_dropped() -> None:
    rows = [{"date": "2026-08-20 08:30:00", "country": "US", "event": "CPI"}]

    assert _normalise_upcoming_events(rows, now=NOW) == []


def test_upcoming_events_are_returned_in_chronological_order() -> None:
    rows = [
        {"date": "2026-08-25 08:30:00", "country": "US", "event": "CPI"},
        {"date": "2026-08-22 08:30:00", "country": "US", "event": "FOMC Rate Decision"},
    ]

    events = _normalise_upcoming_events(rows, now=NOW)

    assert [event["name"] for event in events] == ["FOMC Rate Decision", "CPI"]


def test_a_midnight_event_time_is_reported_as_unannounced() -> None:
    rows = [{"date": "2026-08-25 00:00:00", "country": "US", "event": "CPI"}]

    assert _normalise_upcoming_events(rows, now=NOW)[0]["time"] == "TBA"


def test_a_timed_event_reports_eastern_time() -> None:
    rows = [{"date": "2026-08-25 08:30:00", "country": "US", "event": "CPI"}]

    assert _normalise_upcoming_events(rows, now=NOW)[0]["time"].endswith("ET")


def test_relevance_filtering_can_be_switched_off() -> None:
    rows = [{"date": "2026-08-25 08:30:00", "country": "US", "event": "Widget Shipments"}]

    assert _normalise_upcoming_events(rows, now=NOW) == []
    assert len(_normalise_upcoming_events(rows, now=NOW, require_relevance=False)) == 1


def test_rows_with_no_parseable_date_are_dropped() -> None:
    assert _normalise_upcoming_events([{"country": "US", "event": "CPI"}], now=NOW) == []


# ── summary counts ──────────────────────────────────────────────────────────


def test_summary_counts_report_the_headline_totals() -> None:
    items = [
        _item("Fed holds rates steady", bucket="macro"),
        _item("LQD sees record inflows", bucket="etfs"),
        _item("Treasury curve steepens", bucket="rates"),
    ]

    counts = _compute_summary_counts(items)

    assert counts["market_moving"] == 3
    assert counts["central_bank"] == 1
    assert counts["etf_mentions"] == 1
    assert counts["macro_events"] == 1


def test_top_stories_are_capped_at_five() -> None:
    items = [_item(f"Headline {i}") for i in range(12)]

    assert _compute_summary_counts(items)["top_stories"] == 5


def test_summary_counts_of_an_empty_list_are_all_zero() -> None:
    counts = _compute_summary_counts([])

    assert counts["market_moving"] == 0 and counts["top_stories"] == 0


# ── sentiment ───────────────────────────────────────────────────────────────


def _features(**values: float) -> pd.DataFrame:
    return pd.DataFrame([{"feature_name": name, "value": value} for name, value in values.items()])


def test_sentiment_is_neutral_without_any_features() -> None:
    score, label, description = _compute_sentiment(pd.DataFrame())

    assert (score, label) == (0.0, "Neutral")
    assert "Insufficient" in description


def test_widening_spreads_read_bearish() -> None:
    score, label, _ = _compute_sentiment(_features(IG_OAS_Z20=2.5, HY_OAS_Z20=2.5))

    assert score < 0 and label in {"Bearish", "Cautious"}


def test_tightening_spreads_read_constructive() -> None:
    score, label, _ = _compute_sentiment(_features(IG_OAS_Z20=-2.5, HY_OAS_Z20=-2.5))

    assert score > 0 and label in {"Constructive", "Balanced"}


def test_features_at_their_average_read_neutral() -> None:
    _, label, _ = _compute_sentiment(_features(IG_OAS_Z20=0.0, HY_OAS_Z20=0.0))

    assert label == "Neutral"


def test_the_sentiment_score_is_clamped_to_the_unit_range() -> None:
    for value in (-50.0, 50.0):
        score, _, _ = _compute_sentiment(_features(IG_OAS_Z20=value, HY_OAS_Z20=value))
        assert -1.0 <= score <= 1.0


def test_unrecognised_features_do_not_move_the_score() -> None:
    score, _, _ = _compute_sentiment(_features(SOMETHING_ELSE=5.0))

    assert score == 0.0


def test_a_non_numeric_feature_value_is_skipped() -> None:
    frame = pd.DataFrame([{"feature_name": "IG_OAS_Z20", "value": "n/a"}])

    score, _, _ = _compute_sentiment(frame)

    assert score == 0.0


# ── sparkline ───────────────────────────────────────────────────────────────


def test_a_sparkline_is_drawn_for_a_real_series() -> None:
    svg = _mini_sparkline_svg(pd.Series([1.0, 2.0, 1.5, 3.0]), color="#000000")

    assert svg.startswith("<svg") and "polyline" in svg


def test_a_series_too_short_to_plot_reports_no_trend() -> None:
    assert "No trend" in _mini_sparkline_svg(pd.Series([1.0]), color="#000000")


def test_a_flat_series_still_renders_without_dividing_by_zero() -> None:
    svg = _mini_sparkline_svg(pd.Series([2.0] * 10), color="#000000")

    assert svg.startswith("<svg")
