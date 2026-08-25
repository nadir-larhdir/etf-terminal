from __future__ import annotations

import pandas as pd
import pytest

from dashboard.presenters.macro import MacroRegimes, Regime, StateCard, Tone
from dashboard.render import render


def _levels(**values: float) -> MacroRegimes:
    return MacroRegimes(dict(values))


def _matrix(**values: float) -> pd.DataFrame:
    return pd.DataFrame([values], index=[pd.Timestamp("2026-05-07")])


# ── curve ───────────────────────────────────────────────────────────────────


def test_a_visibly_steep_full_curve_reads_steep() -> None:
    regime = _levels(UST_3M_LEVEL=3.69, UST_30Y_LEVEL=4.98, UST_2S10S=0.50, UST_5S30S=0.90).curve

    assert regime.label == "Curve Steep"
    assert "129 bps" in regime.body


def test_a_visibly_inverted_full_curve_reads_inverted() -> None:
    regime = _levels(UST_3M_LEVEL=5.40, UST_30Y_LEVEL=4.60, UST_2S10S=-0.20).curve

    assert regime.label == "Curve Inverted"
    assert "80 bps" in regime.body


def test_a_compressed_curve_reads_flat_on_both_measures() -> None:
    regime = _levels(UST_3M_LEVEL=4.30, UST_30Y_LEVEL=4.40, UST_2S10S=0.10).curve

    assert regime.label == "Curve Flat"
    assert "compressed" in regime.body


def test_the_curve_falls_back_to_2s10s_when_the_full_curve_is_unavailable() -> None:
    assert _levels(UST_2S10S=-0.30).curve.label == "Curve Inverted"


def test_a_steep_5s30s_alone_is_enough_to_read_steep() -> None:
    assert _levels(UST_2S10S=0.05, UST_5S30S=0.50).curve.label == "Curve Steep"


def test_an_empty_macro_picture_reads_flat_rather_than_failing() -> None:
    assert _levels().curve.label == "Curve Flat"


# ── duration ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("change", "label"),
    [
        (-0.25, "Duration Bullish"),
        (-0.10, "Duration Bullish"),
        (0.0, "Duration Neutral"),
        (0.05, "Duration Neutral"),
        (0.10, "Duration Bearish"),
        (0.40, "Duration Bearish"),
    ],
)
def test_duration_tracks_the_twenty_day_move_in_ten_year_yields(change: float, label: str) -> None:
    assert _levels(UST_10Y_CHANGE_20D=change).duration.label == label


def test_a_falling_yield_is_described_as_a_fall() -> None:
    assert "fallen 25 bps" in _levels(UST_10Y_CHANGE_20D=-0.25).duration.body


def test_a_rising_yield_is_described_as_a_rise() -> None:
    assert "risen 25 bps" in _levels(UST_10Y_CHANGE_20D=0.25).duration.body


# ── inflation ───────────────────────────────────────────────────────────────


def test_headline_inflation_above_three_percent_reads_hot() -> None:
    assert _levels(CPI_YOY=3.4, CPI_3M_ANN=2.0).inflation.label == "Inflation Hot"


def test_a_hot_short_run_pace_alone_reads_hot() -> None:
    assert _levels(CPI_YOY=2.1, CPI_3M_ANN=4.5).inflation.label == "Inflation Hot"


def test_rising_breakevens_read_as_repricing_when_cpi_is_contained() -> None:
    regime = _levels(CPI_YOY=2.1, CPI_3M_ANN=2.0, BEI_5Y_CHANGE_20D=0.30).inflation

    assert regime.label == "Inflation Repricing"
    assert "30 bps" in regime.body


def test_contained_inflation_reads_cooling() -> None:
    assert _levels(CPI_YOY=2.1, CPI_3M_ANN=1.8).inflation.label == "Inflation Cooling"


# ── growth ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("change", "label"),
    [(-0.30, "Growth Improving"), (0.0, "Growth Stable"), (0.30, "Growth Deteriorating")],
)
def test_growth_tracks_the_three_month_change_in_unemployment(change: float, label: str) -> None:
    assert _levels(UNRATE_3M_CHANGE=change).growth.label == label


def test_falling_unemployment_is_described_as_a_fall() -> None:
    assert "fallen 30 bps" in _levels(UNRATE_3M_CHANGE=-0.30).growth.body


# ── assembly ────────────────────────────────────────────────────────────────


def test_all_four_regimes_are_reported_together() -> None:
    regimes = MacroRegimes.from_matrix(
        _matrix(UST_2S10S=0.5, UST_10Y_CHANGE_20D=0.2, CPI_YOY=2.0, UNRATE_3M_CHANGE=0.0)
    ).all()

    assert set(regimes) == {
        "duration_regime",
        "curve_regime",
        "inflation_regime",
        "growth_regime",
    }
    assert all(isinstance(regime, Regime) for regime in regimes.values())


def test_a_regime_unpacks_as_a_label_and_body_pair() -> None:
    label, body = Regime("Curve Steep", "3M-to-30Y slopes upward.")

    assert label == "Curve Steep" and body.startswith("3M")


def test_from_matrix_reads_the_most_recent_observation() -> None:
    matrix = pd.DataFrame(
        {"UST_10Y_CHANGE_20D": [0.5, -0.5]}, index=pd.bdate_range("2026-05-06", periods=2)
    )

    assert MacroRegimes.from_matrix(matrix).duration.label == "Duration Bullish"


def test_from_matrix_ignores_trailing_gaps() -> None:
    matrix = pd.DataFrame(
        {"UST_10Y_CHANGE_20D": [-0.5, float("nan")]},
        index=pd.bdate_range("2026-05-06", periods=2),
    )

    assert MacroRegimes.from_matrix(matrix).duration.label == "Duration Bullish"


# ── tone ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "tone"),
    [(1.0, Tone.POSITIVE), (-1.0, Tone.NEGATIVE), (0.0, Tone.NEUTRAL), (None, Tone.NEUTRAL)],
)
def test_tone_follows_the_sign_of_the_change(value: float | None, tone: Tone) -> None:
    assert Tone.from_change(value) is tone


def test_a_missing_change_is_neutral() -> None:
    assert Tone.from_change(float("nan")) is Tone.NEUTRAL


@pytest.mark.parametrize(
    ("tone", "arrow"), [(Tone.POSITIVE, "↑"), (Tone.NEGATIVE, "↓"), (Tone.NEUTRAL, "→")]
)
def test_each_tone_carries_its_own_arrow(tone: Tone, arrow: str) -> None:
    assert tone.arrow == arrow
    assert tone.delta_class.endswith(tone.slug)


# ── state card template ─────────────────────────────────────────────────────


def test_a_state_card_renders_its_level_change_and_badge() -> None:
    card = StateCard(
        label="10Y Yield",
        value="4.37%",
        delta="+3.1 bps",
        delta_tone=Tone.POSITIVE,
        badge="Z20 z +1.20",
        badge_tone=Tone.POSITIVE,
    )

    html = render("macro/state_card.html", card=card)

    assert "10Y YIELD" in html
    assert "4.37%" in html and "+3.1 bps" in html
    assert "Z20 z +1.20" in html


def test_a_state_card_without_a_badge_omits_the_badge_row() -> None:
    card = StateCard(label="10Y", value="4.37%", delta="+3.1 bps", delta_tone=Tone.POSITIVE)

    assert "bb-regime-badge" not in render("macro/state_card.html", card=card)
