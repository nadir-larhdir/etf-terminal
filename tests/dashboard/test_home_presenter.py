from __future__ import annotations

import pandas as pd
import pytest

from dashboard.presenters import DirectionBadge, HomePresenter, RegimeCard, SnapshotTile
from fixed_income.analytics.result_models import RegimeSnapshot

DATES = pd.bdate_range("2026-08-17", periods=3)


def _history(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes, "volume": volumes or [1_000_000.0] * len(closes)},
        index=pd.bdate_range("2026-08-17", periods=len(closes)),
    )


def _universe(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ticker", "asset_class"])


def _presenter() -> HomePresenter:
    return HomePresenter()


def _histories(**frames: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The trailing price history per ticker, as the page fetches it."""
    return dict(frames)


# ── snapshot tiles ──────────────────────────────────────────────────────────


def test_snapshot_tile_marks_a_rise_up_and_a_fall_down() -> None:
    up = SnapshotTile.from_move("UST_10Y_LEVEL", "US 10Y", "UST", 4.37, 0.02)
    down = SnapshotTile.from_move("UST_10Y_LEVEL", "US 10Y", "UST", 4.37, -0.02)

    assert (up.indicator, up.delta_class) == ("▲", "home-delta-up")
    assert (down.indicator, down.delta_class) == ("▼", "home-delta-down")


def test_snapshot_tile_marks_an_unchanged_reading_flat() -> None:
    flat = SnapshotTile.from_move("UST_10Y_LEVEL", "US 10Y", "UST", 4.37, 0.0)

    assert (flat.indicator, flat.delta_class) == ("•", "home-delta-flat")


def test_snapshot_tile_quotes_each_feature_in_its_own_unit() -> None:
    rate = SnapshotTile.from_move("UST_10Y_LEVEL", "US 10Y", "UST", 4.37, 0.031)
    spread = SnapshotTile.from_move("HY_OAS_LEVEL", "HY OAS", "Spread", 3.20, -0.05)

    assert rate.value == "4.37%" and rate.delta == "+3.1 bps"
    assert spread.value == "320 bps" and spread.delta == "-5.0 bps"


def test_snapshot_tiles_are_empty_without_stored_features() -> None:
    assert _presenter().snapshot_tiles(pd.DataFrame()) == []


def test_snapshot_tiles_skip_features_with_no_observations() -> None:
    matrix = pd.DataFrame(
        {"UST_10Y_LEVEL": [4.3, 4.35], "HY_OAS_LEVEL": [float("nan")] * 2}, index=DATES[:2]
    )

    tiles = _presenter().snapshot_tiles(matrix)

    assert [tile.label for tile in tiles] == ["US 10Y"]


def test_a_single_observation_reports_no_move_rather_than_failing() -> None:
    matrix = pd.DataFrame({"UST_10Y_LEVEL": [4.3]}, index=DATES[:1])

    tile = _presenter().snapshot_tiles(matrix)[0]

    assert tile.indicator == "•"


def test_snapshot_tiles_are_capped_at_the_strip_width() -> None:
    matrix = pd.DataFrame(
        {name: [1.0, 1.1] for name in HomePresenter.SNAPSHOT_FEATURES}, index=DATES[:2]
    )

    tiles = _presenter().snapshot_tiles(matrix)

    assert len(tiles) == min(7, len(HomePresenter.SNAPSHOT_FEATURES))


# ── regime card ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "accent"),
    [("Risk Off", "#FF5A36"), ("Neutral", "#FFD166"), ("Risk On", "#00C176")],
)
def test_regime_card_pairs_each_label_with_its_accent(label: str, accent: str) -> None:
    card = RegimeCard.from_snapshot(
        RegimeSnapshot(label=label, composite_zscore=0.0, position=50.0)
    )

    assert card.accent == accent
    assert card.body


def test_regime_card_falls_back_rather_than_raising_on_an_unknown_label() -> None:
    card = RegimeCard.from_snapshot(
        RegimeSnapshot(label="Unclassified", composite_zscore=0.0, position=50.0)
    )

    assert card.label == "Unclassified"
    assert card.accent == RegimeCard.FALLBACK[0]


def test_regime_card_carries_the_gauge_position_through_unchanged() -> None:
    card = RegimeCard.from_snapshot(
        RegimeSnapshot(label="Risk On", composite_zscore=1.2, position=73.6)
    )

    assert card.position == 73.6


# ── market date, leaders, stats ─────────────────────────────────────────────


def test_latest_market_date_is_the_newest_across_the_universe() -> None:
    histories = _histories(
        IEF=_history([100.0, 101.0]).iloc[:1], HYG=_history([100.0, 101.0, 102.0])
    )

    assert _presenter().latest_market_date(histories) == "2026-08-19"


def test_latest_market_date_falls_back_when_nothing_is_stored() -> None:
    assert _presenter().latest_market_date({}) == HomePresenter.NO_HISTORY_LABEL


def test_volume_leaders_rank_by_activity_against_each_name_s_own_average() -> None:
    histories = _histories(
        QUIET=_history([100.0] * 31, [1_000_000.0] * 30 + [500_000.0]),
        BUSY=_history([100.0] * 31, [1_000_000.0] * 30 + [3_000_000.0]),
    )

    leaders = _presenter().volume_leaders(histories)

    assert leaders[0].startswith("BUSY")


def test_volume_leaders_report_a_real_ratio_not_a_flat_one() -> None:
    """With only the latest session in hand the baseline equals the latest bar and every
    name scored exactly x1.00, which made the ranking meaningless."""
    histories = _histories(BUSY=_history([100.0] * 31, [1_000_000.0] * 30 + [3_000_000.0]))

    assert _presenter().volume_leaders(histories) != ["BUSY (x1.00)"]


def test_a_single_session_cannot_be_ranked_and_scores_flat() -> None:
    histories = _histories(ONEDAY=_history([100.0], [1_000_000.0]))

    assert _presenter().volume_leaders(histories) == ["ONEDAY (x1.00)"]


def test_volume_leaders_are_empty_when_no_history_is_stored() -> None:
    assert _presenter().volume_leaders({}) == []


def test_volume_leaders_skip_names_with_no_volume_column() -> None:
    histories = _histories(IEF=pd.DataFrame({"close": [100.0]}, index=DATES[:1]))

    assert _presenter().volume_leaders(histories) == []


def test_stat_cards_report_the_counts_they_are_given() -> None:
    cards = _presenter().stat_cards(active_etfs=42, bucket_count=7, latest_date="2026-08-21")

    assert [card.value for card in cards] == ["42", "7", "2026-08-21"]
    assert [card.icon for card in cards] == ["active", "bucket", "calendar"]


# ── universe summary ────────────────────────────────────────────────────────


def test_bucket_summary_of_an_empty_universe_keeps_its_columns() -> None:
    summary = _presenter().bucket_summary(pd.DataFrame(), {})

    assert summary.empty
    assert list(summary.columns) == ["ASSET CLASS", "ETF COUNT", "EXAMPLE TICKERS", "VS 1D"]


def test_bucket_summary_groups_and_orders_by_size() -> None:
    histories = {t: _history([100.0, 101.0]) for t in ("A", "B", "C")}

    summary = _presenter().bucket_summary(
        _universe([("A", "IG Credit"), ("B", "IG Credit"), ("C", "MBS")]), histories
    )

    assert summary.iloc[0]["ASSET CLASS"] == "IG Credit"
    assert summary.iloc[0]["ETF COUNT"] == 2


def test_bucket_summary_normalizes_asset_class_aliases() -> None:
    histories = {"A": _history([100.0, 101.0])}

    summary = _presenter().bucket_summary(_universe([("A", "CREDIT IG")]), histories)

    assert summary.iloc[0]["ASSET CLASS"] == "IG Credit"


def test_bucket_summary_nets_daily_direction_across_the_bucket() -> None:
    histories = {"UP": _history([100.0, 101.0]), "DOWN": _history([100.0, 99.0])}

    summary = _presenter().bucket_summary(_universe([("UP", "MBS"), ("DOWN", "MBS")]), histories)

    assert summary.iloc[0]["VS 1D"] == 0


def test_bucket_summary_treats_a_single_close_as_flat() -> None:
    summary = _presenter().bucket_summary(_universe([("A", "MBS")]), {"A": _history([100.0])})

    assert summary.iloc[0]["VS 1D"] == 0


@pytest.mark.parametrize(
    ("net", "label"),
    [(3, "Broad"), (1, "Firm"), (0, "Stable"), (-1, "Soft"), (-3, "Weakening")],
)
def test_direction_badge_describes_the_net_move(net: int, label: str) -> None:
    assert DirectionBadge.from_net(net).label == label


# ── market pulse ────────────────────────────────────────────────────────────


def test_the_most_active_names_are_a_pulse_row_like_every_other_line() -> None:
    rows = _presenter().pulse_rows(["AGG (x1.20)", "HYG (x1.10)"])

    most_active = rows[-1]
    assert most_active.title == "Most Active"
    assert most_active.body == "AGG (x1.20), HYG (x1.10)"
    assert most_active.tag == "TOP 2"


def test_the_pulse_card_omits_the_most_active_row_when_nothing_is_trading() -> None:
    rows = _presenter().pulse_rows([])

    assert [row.title for row in rows] == [row.title for row in HomePresenter.PULSE_ROWS]


def test_every_pulse_row_carries_the_same_fields() -> None:
    for row in _presenter().pulse_rows(["AGG (x1.20)"]):
        assert row.title and row.body and row.tag and row.tag_class


def test_the_pulse_template_renders_the_most_active_row_in_the_shared_markup() -> None:
    from dashboard.render import render

    html = render("home/pulse_card.html", rows=_presenter().pulse_rows(["AGG (x1.20)"]))

    assert html.count("home-pulse-row") == len(HomePresenter.PULSE_ROWS) + 1
    assert "Most Active" in html and "AGG (x1.20)" in html


# ── context cards ───────────────────────────────────────────────────────────


def test_three_context_cards_are_offered() -> None:
    assert len(_presenter().context_cards()) == 3


def test_the_news_card_links_through_to_the_news_view() -> None:
    news = next(card for card in _presenter().context_cards() if card.cta_view)

    assert news.cta_view == "News"
    assert news.cta_label.startswith("View latest news")


def test_the_explanatory_cards_offer_no_link() -> None:
    linked = [card for card in _presenter().context_cards() if card.cta_view]

    assert len(linked) == 1


MAX_CONTEXT_TITLE = 40
MAX_CONTEXT_BODY = 160


def test_the_context_copy_stays_short_enough_to_keep_the_row_shallow() -> None:
    """The cards are equal height, so the longest body sets how far down the page the
    Universe Snapshot starts. Verbose copy pushes the table off the fold."""
    for card in _presenter().context_cards():
        assert len(card.title) <= MAX_CONTEXT_TITLE, card.kicker
        assert len(card.body) <= MAX_CONTEXT_BODY, card.kicker


def test_the_context_cards_are_balanced_in_length() -> None:
    """A card far longer than its neighbours leaves the others padded with dead space."""
    lengths = [len(card.body) for card in _presenter().context_cards()]

    assert max(lengths) - min(lengths) <= 60


def test_a_card_ending_in_copy_reserves_space_below_its_last_line() -> None:
    from dashboard.render import render

    ending_in_copy = next(c for c in _presenter().context_cards() if not c.cta_view)

    assert "home-context-body--tail" in render("home/context_card.html", card=ending_in_copy)


def test_a_card_ending_in_a_link_does_not_double_up_the_spacing() -> None:
    from dashboard.render import render

    ending_in_link = next(c for c in _presenter().context_cards() if c.cta_view)

    assert "home-context-body--tail" not in render("home/context_card.html", card=ending_in_link)


def test_a_context_card_renders_its_kicker_title_and_body() -> None:
    from dashboard.render import render

    card = _presenter().context_cards()[0]
    html = render("home/context_card.html", card=card)

    assert card.kicker in html and card.title in html
