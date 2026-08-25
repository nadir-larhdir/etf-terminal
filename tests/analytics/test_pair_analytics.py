from __future__ import annotations

import math

import pandas as pd
import pytest

from fixed_income.etfs import ETF
from fixed_income.rv.pair_analytics import (
    StabilityScore,
    aligned_prices,
    beta_metrics,
    filtered_prices,
    half_life_from_autocorr,
    ratio,
    returns_from_prices,
    rolling_correlation,
    screener_snapshot,
)
from fixed_income.rv.spread_definition import SpreadDefinition

DEFINITION = SpreadDefinition("LQD", "IEF")


def _history(prices: list[float], adj_prices: list[float] | None = None) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=len(prices))
    adjusted = adj_prices or prices
    return pd.DataFrame(
        {
            "close": prices,
            "adj_close": adjusted,
            "open": prices,
            "high": [p * 1.001 for p in prices],
            "low": [p * 0.999 for p in prices],
            "volume": 1_000_000.0,
        },
        index=index,
    )


def _pair(left_prices: list[float], right_prices: list[float]) -> tuple[ETF, ETF]:
    return ETF("LQD", history=_history(left_prices)), ETF("IEF", history=_history(right_prices))


def _wave(n: int, amplitude: float = 2.0, base: float = 100.0) -> list[float]:
    return [base + amplitude * math.sin(i / 3.0) for i in range(n)]


def test_ratio_uses_adjusted_close_not_close() -> None:
    left = ETF("LQD", history=_history([100, 100], adj_prices=[50, 60]))
    right = ETF("IEF", history=_history([100, 100], adj_prices=[25, 30]))

    assert ratio(left, right).tolist() == [2.0, 2.0]


def test_aligned_prices_keeps_only_common_dates() -> None:
    left, right = _pair([100, 101, 102], [95, 96, 97])
    right.history = right.history.iloc[1:]

    assert len(aligned_prices(left, right)) == 2


def test_aligned_prices_is_empty_when_a_leg_has_no_history() -> None:
    left, _ = _pair([100, 101], [95, 96])

    assert aligned_prices(left, ETF("IEF")).empty


def test_filtered_prices_honours_both_range_bounds() -> None:
    left, right = _pair([100, 101, 102, 103, 104], [95, 96, 97, 98, 99])
    index = left.history.index

    result = filtered_prices(left, right, start_date=index[1], end_date=index[3])

    assert result.index.tolist() == index[1:4].tolist()


def test_filtered_prices_returns_empty_for_a_range_outside_the_history() -> None:
    left, right = _pair([100, 101], [95, 96])

    assert filtered_prices(left, right, start_date="2030-01-01").empty


def test_returns_from_prices_renames_the_legs() -> None:
    left, right = _pair([100, 110], [95, 95])

    assert list(returns_from_prices(aligned_prices(left, right)).columns) == [
        "ret_left",
        "ret_right",
    ]


def test_returns_from_prices_of_an_empty_frame_is_empty() -> None:
    assert returns_from_prices(pd.DataFrame()).empty


def test_rolling_correlation_of_identical_legs_is_one() -> None:
    prices = _wave(40)
    left, right = _pair(prices, prices)

    assert rolling_correlation(left, right, window=20).dropna().iloc[-1] == pytest.approx(1.0)


def test_rolling_correlation_is_empty_without_history() -> None:
    assert rolling_correlation(ETF("LQD"), ETF("IEF")).empty


@pytest.mark.parametrize("autocorr", [None, 0.0, 1.0, 1.5, -0.3])
def test_half_life_is_undefined_outside_the_mean_reverting_range(autocorr: float | None) -> None:
    assert half_life_from_autocorr(autocorr) is None


def test_half_life_matches_the_analytic_ou_value() -> None:
    assert half_life_from_autocorr(0.5) == pytest.approx(1.0)


def test_stability_score_is_bounded_and_peaks_at_the_target_half_life() -> None:
    perfect = StabilityScore(correlation=1.0, half_life_days=10.0, beta_dispersion=0.0)

    assert perfect.value == pytest.approx(100.0)


def test_stability_score_floors_at_zero_when_every_component_is_degenerate() -> None:
    worst = StabilityScore(correlation=0.0, half_life_days=None, beta_dispersion=1e9)

    assert worst.value == pytest.approx(0.0, abs=1e-3)


def test_stability_score_clamps_a_far_off_half_life_instead_of_going_negative() -> None:
    far_off = StabilityScore(correlation=0.0, half_life_days=500.0, beta_dispersion=1e9)

    assert far_off.value >= 0.0


def test_stability_score_treats_negative_correlation_as_equally_tradable() -> None:
    positive = StabilityScore(correlation=0.9, half_life_days=10.0, beta_dispersion=0.0)
    negative = StabilityScore(correlation=-0.9, half_life_days=10.0, beta_dispersion=0.0)

    assert positive.value == pytest.approx(negative.value)


def test_screener_snapshot_reports_a_bounded_summary_row() -> None:
    left, right = _pair(_wave(60), _wave(60, amplitude=1.0, base=95.0))

    snapshot = screener_snapshot(DEFINITION, left, right)

    assert snapshot.name == "LQD/IEF"
    assert -1.0 <= snapshot.correlation_20d <= 1.0
    assert 0.0 <= snapshot.stability <= 100.0


def test_screener_snapshot_is_neutral_when_the_pair_has_no_overlap() -> None:
    snapshot = screener_snapshot(DEFINITION, ETF("LQD"), ETF("IEF"))

    assert (snapshot.zscore, snapshot.correlation_20d, snapshot.stability) == (0.0, 0.0, 0.0)


def _compounded(returns: list[float], base: float = 100.0) -> list[float]:
    """Build a price path whose simple returns are exactly the given sequence."""
    prices = [base]
    for r in returns:
        prices.append(prices[-1] * (1.0 + r))
    return prices


def test_beta_metrics_recovers_a_known_hedge_ratio() -> None:
    daily = [math.sin(i / 3.0) * 0.01 for i in range(59)]
    left, right = _pair(_compounded([2 * r for r in daily]), _compounded(daily))

    beta, spread, zscore = beta_metrics(left, right)

    assert beta == pytest.approx(2.0, abs=0.05)
    assert len(spread) == len(zscore) == 60


def test_beta_metrics_honours_an_externally_supplied_beta() -> None:
    left, right = _pair([100.0] * 5, [50.0] * 5)

    beta, spread, _ = beta_metrics(left, right, beta=2.0)

    assert beta == 2.0
    assert spread.tolist() == [0.0] * 5


def test_beta_metrics_returns_empty_series_without_price_overlap() -> None:
    _, spread, zscore = beta_metrics(ETF("LQD"), ETF("IEF"))

    assert spread.empty and zscore.empty
