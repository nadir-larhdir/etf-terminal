from __future__ import annotations

import pandas as pd

from dashboard.pages.macro_page import MacroPage


def _one_row_matrix(**values: float) -> pd.DataFrame:
    return pd.DataFrame([values], index=[pd.Timestamp("2026-05-07")])


def test_curve_regime_uses_full_curve_when_visibly_steep() -> None:
    page = MacroPage(macro_feature_store=None)
    matrix = _one_row_matrix(
        UST_3M_LEVEL=3.69,
        UST_2Y_LEVEL=3.93,
        UST_10Y_LEVEL=4.43,
        UST_30Y_LEVEL=4.98,
        UST_2S10S=0.50,
        UST_5S30S=0.90,
    )

    headline, body = page._rule_based_regimes(matrix)["curve_regime"]

    assert headline == "Curve Steep"
    assert "129 bps" in body


def test_curve_regime_can_still_label_compressed_curve_flat() -> None:
    page = MacroPage(macro_feature_store=None)
    matrix = _one_row_matrix(
        UST_3M_LEVEL=4.20,
        UST_2Y_LEVEL=4.25,
        UST_10Y_LEVEL=4.35,
        UST_30Y_LEVEL=4.40,
        UST_2S10S=0.10,
        UST_5S30S=0.12,
    )

    headline, body = page._rule_based_regimes(matrix)["curve_regime"]

    assert headline == "Curve Flat"
    assert "compressed" in body


def test_duration_regime_uses_bps_thresholds_for_10y_changes() -> None:
    page = MacroPage(macro_feature_store=None)

    bullish = page._rule_based_regimes(_one_row_matrix(UST_10Y_CHANGE_20D=-0.12))
    neutral = page._rule_based_regimes(_one_row_matrix(UST_10Y_CHANGE_20D=0.05))
    bearish = page._rule_based_regimes(_one_row_matrix(UST_10Y_CHANGE_20D=0.15))

    assert bullish["duration_regime"][0] == "Duration Bullish"
    assert "12 bps" in bullish["duration_regime"][1]
    assert neutral["duration_regime"][0] == "Duration Neutral"
    assert bearish["duration_regime"][0] == "Duration Bearish"
    assert "15 bps" in bearish["duration_regime"][1]


def test_inflation_regime_uses_percent_and_bps_thresholds() -> None:
    page = MacroPage(macro_feature_store=None)

    hot = page._rule_based_regimes(_one_row_matrix(CPI_YOY=3.2, CPI_3M_ANN=2.4))
    repricing = page._rule_based_regimes(
        _one_row_matrix(CPI_YOY=2.4, CPI_3M_ANN=2.2, BEI_5Y_CHANGE_20D=0.28)
    )
    cooling = page._rule_based_regimes(
        _one_row_matrix(CPI_YOY=2.4, CPI_3M_ANN=2.2, BEI_5Y_CHANGE_20D=0.05)
    )

    assert hot["inflation_regime"][0] == "Inflation Hot"
    assert repricing["inflation_regime"][0] == "Inflation Repricing"
    assert "28 bps" in repricing["inflation_regime"][1]
    assert cooling["inflation_regime"][0] == "Inflation Cooling"


def test_growth_regime_uses_bps_thresholds_for_unemployment_changes() -> None:
    page = MacroPage(macro_feature_store=None)

    improving = page._rule_based_regimes(_one_row_matrix(UNRATE_3M_CHANGE=-0.15))
    stable = page._rule_based_regimes(_one_row_matrix(UNRATE_3M_CHANGE=0.05))
    deteriorating = page._rule_based_regimes(_one_row_matrix(UNRATE_3M_CHANGE=0.20))

    assert improving["growth_regime"][0] == "Growth Improving"
    assert "15 bps" in improving["growth_regime"][1]
    assert stable["growth_regime"][0] == "Growth Stable"
    assert deteriorating["growth_regime"][0] == "Growth Deteriorating"
    assert "20 bps" in deteriorating["growth_regime"][1]
