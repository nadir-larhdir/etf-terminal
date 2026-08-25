"""Formatting and styling applied to the dashboard's tabular output."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dashboard.styles.table_styles import DashboardTable

TABLE = DashboardTable()


# ── price history ───────────────────────────────────────────────────────────


def test_price_columns_are_shown_to_two_decimals() -> None:
    frame = pd.DataFrame({"open": [100.0], "high": [101.5], "low": [99.25], "close": [100.756]})

    formatted = TABLE.format_history(frame)

    assert formatted["close"].iloc[0] == "100.76"
    assert formatted["low"].iloc[0] == "99.25"


def test_large_prices_are_thousands_separated() -> None:
    formatted = TABLE.format_history(pd.DataFrame({"close": [12345.678]}))

    assert formatted["close"].iloc[0] == "12,345.68"


def test_volume_is_shown_as_a_separated_integer() -> None:
    formatted = TABLE.format_history(pd.DataFrame({"volume": [1234567.0]}))

    assert formatted["volume"].iloc[0] == "1,234,567"


def test_dates_are_normalised_to_iso() -> None:
    formatted = TABLE.format_history(pd.DataFrame({"date": ["2026-08-21T13:45:00"]}))

    assert formatted["date"].iloc[0] == "2026-08-21"


def test_missing_values_render_as_blanks_rather_than_nan() -> None:
    formatted = TABLE.format_history(pd.DataFrame({"close": [np.nan], "volume": [np.nan]}))

    assert formatted["close"].iloc[0] == ""
    assert formatted["volume"].iloc[0] == ""


def test_formatting_leaves_the_original_frame_untouched() -> None:
    frame = pd.DataFrame({"close": [100.0]})

    TABLE.format_history(frame)

    assert frame["close"].iloc[0] == 100.0


def test_a_frame_without_price_columns_passes_through() -> None:
    frame = pd.DataFrame({"note": ["hello"]})

    assert TABLE.format_history(frame)["note"].iloc[0] == "hello"


# ── signal history ──────────────────────────────────────────────────────────


def test_the_signal_history_date_is_normalised_to_iso() -> None:
    frame = pd.DataFrame({"DATE": [pd.Timestamp("2026-08-21 09:30")], "Z-SCORE": ["1.20"]})

    assert TABLE.format_signal_history(frame)["DATE"].iloc[0] == "2026-08-21"


def test_signal_history_without_a_date_column_passes_through() -> None:
    frame = pd.DataFrame({"Z-SCORE": ["1.20"]})

    assert TABLE.format_signal_history(frame).equals(frame)


# ── RV screener ─────────────────────────────────────────────────────────────


def _screener(**columns: object) -> pd.DataFrame:
    return pd.DataFrame({key: [value] for key, value in columns.items()})


@pytest.mark.parametrize("column", ["SPREAD DEV", "FWD 10D RET", "FWD 20D RET", "RATIO DEV"])
def test_percentage_columns_are_signed_to_two_decimals(column: str) -> None:
    formatted = TABLE.format_screener(_screener(**{column: 1.2345}))

    assert formatted[column].iloc[0] == "+1.23%"


def test_a_negative_percentage_keeps_its_sign() -> None:
    assert (
        TABLE.format_screener(_screener(**{"SPREAD DEV": -1.2}))["SPREAD DEV"].iloc[0] == "-1.20%"
    )


def test_half_life_is_shown_in_days() -> None:
    assert TABLE.format_screener(_screener(**{"HALF-LIFE": 5.24}))["HALF-LIFE"].iloc[0] == "5.2d"


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_a_non_positive_half_life_is_shown_as_unavailable(value: float) -> None:
    assert TABLE.format_screener(_screener(**{"HALF-LIFE": value}))["HALF-LIFE"].iloc[0] == "--"


def test_stability_is_rounded_to_a_whole_number() -> None:
    assert TABLE.format_screener(_screener(STABILITY=73.6))["STABILITY"].iloc[0] == "74"


def test_text_columns_are_left_as_they_are() -> None:
    formatted = TABLE.format_screener(
        _screener(PAIR="LQD/IEF", REGIME="RICH", ACTION="<span>WATCH</span>")
    )

    assert formatted["PAIR"].iloc[0] == "LQD/IEF"
    assert formatted["REGIME"].iloc[0] == "RICH"
    assert formatted["ACTION"].iloc[0] == "<span>WATCH</span>"


def test_other_numeric_columns_default_to_two_decimals() -> None:
    assert TABLE.format_screener(_screener(**{"Z-SCORE": 1.239}))["Z-SCORE"].iloc[0] == "1.24"


def test_missing_screener_values_render_as_blanks() -> None:
    assert TABLE.format_screener(_screener(**{"Z-SCORE": np.nan}))["Z-SCORE"].iloc[0] == ""


# ── display preparation ─────────────────────────────────────────────────────


def test_whole_number_columns_are_shown_without_decimals() -> None:
    prepared = TABLE._prepare_display_dataframe(pd.DataFrame({"ETF COUNT": [12, 7]}))

    assert list(prepared["ETF COUNT"]) == ["12", "7"]


def test_fractional_columns_are_shown_to_two_decimals() -> None:
    prepared = TABLE._prepare_display_dataframe(pd.DataFrame({"BETA": [1.2345]}))

    assert prepared["BETA"].iloc[0] == "1.23"


def test_reserved_text_columns_are_never_reformatted() -> None:
    frame = pd.DataFrame({"PAIR": ["LQD/IEF"], "DATE": ["2026-08-21"], "REGIME": ["RICH"]})

    prepared = TABLE._prepare_display_dataframe(frame)

    assert prepared.equals(frame)


def test_a_non_numeric_column_is_left_alone() -> None:
    frame = pd.DataFrame({"EXAMPLE TICKERS": ["LQD, HYG"]})

    assert TABLE._prepare_display_dataframe(frame).equals(frame)


# ── cell styling ────────────────────────────────────────────────────────────


def _styles(frame: pd.DataFrame) -> str:
    """Rendered styles with whitespace normalised, since pandas spaces its declarations."""
    return "".join(TABLE._style_dataframe(frame).to_html().split())


def test_a_positive_z_score_is_styled_green_and_a_negative_one_red() -> None:
    html = _styles(pd.DataFrame({"Z-SCORE": ["1.50", "-1.50"]}))

    assert "#4E7B52" in html and "#A55C45" in html


def test_an_extreme_z_score_is_emphasised() -> None:
    assert "font-weight:700" in _styles(pd.DataFrame({"Z-SCORE": ["2.50"]}))


def test_a_rich_regime_cell_is_coloured_as_a_short() -> None:
    assert "#A55C45" in _styles(pd.DataFrame({"REGIME": ["RICH"]}))


def test_a_cheap_regime_cell_is_coloured_as_a_long() -> None:
    assert "#4E7B52" in _styles(pd.DataFrame({"REGIME": ["CHEAP"]}))


def test_a_strong_correlation_is_emphasised() -> None:
    assert "font-weight:700" in _styles(pd.DataFrame({"CORR (60D)": ["0.90"]}))


def test_a_numeric_cell_is_right_aligned_and_a_pair_label_left_aligned() -> None:
    assert "text-align:right" in _styles(pd.DataFrame({"BETA": ["1.20"]}))
    assert "text-align:left" in _styles(pd.DataFrame({"PAIR": ["LQD/IEF"]}))
