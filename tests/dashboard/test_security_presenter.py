from __future__ import annotations

import pandas as pd
import pytest

from dashboard.presenters import PriceCard, metadata_rows
from dashboard.render import render


def _history(closes: list[float], volumes: list[float] | None = None) -> pd.DataFrame:
    return pd.DataFrame(
        {"close": closes, "volume": volumes or [1_000_000.0] * len(closes)},
        index=pd.bdate_range("2026-08-17", periods=len(closes)),
    )


def _labels(rows: list[tuple[str, str]]) -> dict[str, str]:
    return dict(rows)


# ── price card ──────────────────────────────────────────────────────────────


def test_a_rising_day_is_signed_and_marked_positive() -> None:
    card = PriceCard.from_history("LQD", _history([100.0, 102.5]))

    assert card is not None
    assert card.price == "102.50"
    assert card.change == "+2.50"
    assert card.change_percent == "+2.50%"
    assert card.change_class == "db-price-pos"


def test_a_falling_day_is_marked_negative() -> None:
    card = PriceCard.from_history("LQD", _history([100.0, 97.5]))

    assert card is not None
    assert card.change == "-2.50"
    assert card.change_class == "db-price-neg"


def test_an_unchanged_day_reads_as_positive_zero() -> None:
    card = PriceCard.from_history("LQD", _history([100.0, 100.0]))

    assert card is not None
    assert card.change == "+0.00"
    assert card.change_class == "db-price-pos"


def test_a_single_close_reports_no_change_rather_than_failing() -> None:
    card = PriceCard.from_history("LQD", _history([100.0]))

    assert card is not None
    assert card.change == "+0.00"


def test_a_zero_previous_close_does_not_divide_by_zero() -> None:
    card = PriceCard.from_history("LQD", _history([0.0, 100.0]))

    assert card is not None
    assert card.change_percent == "+0.00%"


def test_large_prices_are_thousands_separated() -> None:
    card = PriceCard.from_history("LQD", _history([1000.0, 12345.678]))

    assert card is not None and card.price == "12,345.68"


@pytest.mark.parametrize(
    "history",
    [pd.DataFrame(), pd.DataFrame({"volume": [1.0]}), pd.DataFrame({"close": [float("nan")]})],
    ids=["empty", "no-close-column", "all-nan"],
)
def test_there_is_no_card_without_a_usable_close(history: pd.DataFrame) -> None:
    assert PriceCard.from_history("LQD", history) is None


def test_the_card_template_renders_the_ticker_and_both_changes() -> None:
    card = PriceCard.from_history("LQD", _history([100.0, 102.5]))

    html = render("security/price_card.html", card=card)

    assert "LQD · PX_LAST" in html
    assert "+2.50" in html and "+2.50%" in html


# ── metadata panel ──────────────────────────────────────────────────────────


def test_metadata_rows_render_the_populated_fields() -> None:
    metadata = {
        "category": "IG Credit",
        "benchmark_index": "Markit iBoxx",
        "duration_bucket": "Belly",
        "issuer": "iShares",
        "yield_to_maturity": 4.82,
        "total_assets": 32_400_000_000,
        "expense_ratio": 0.14,
    }

    rows = _labels(metadata_rows(metadata, _history([100.0] * 31)))

    assert rows["Category"] == "IG Credit"
    assert rows["YTM"] == "4.82%"
    assert rows["AUM"] == "32.4B"
    assert rows["Exp Ratio"] == "0.14%"


def test_missing_metadata_fields_fall_back_to_the_placeholder() -> None:
    rows = _labels(metadata_rows({}, pd.DataFrame()))

    assert set(rows.values()) == {"N/A"}


def test_an_empty_string_field_is_treated_as_missing() -> None:
    rows = _labels(metadata_rows({"issuer": ""}, pd.DataFrame()))

    assert rows["Issuer"] == "N/A"


def test_liquidity_reports_volume_against_its_thirty_day_average() -> None:
    history = _history([100.0] * 31, [1_000_000.0] * 30 + [2_000_000.0])

    rows = _labels(metadata_rows({}, history))

    assert rows["Liquidity"] == "x1.94"


def test_liquidity_is_unavailable_without_volume_history() -> None:
    rows = _labels(metadata_rows({}, pd.DataFrame({"close": [100.0]})))

    assert rows["Liquidity"] == "N/A"


def test_the_panel_template_renders_one_row_per_field() -> None:
    rows = metadata_rows({"category": "IG Credit"}, pd.DataFrame())

    html = render("security/metadata_panel.html", rows=rows)

    assert html.count("db-meta-row") == len(rows)
    assert "IG Credit" in html
