from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fixed_income.series import (
    RollingWindow,
    beta,
    log_returns,
    simple_returns,
    zscore,
)


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, index=pd.bdate_range("2025-01-01", periods=len(values)), dtype=float)


def test_rolling_window_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError, match="window must be >= 1"):
        RollingWindow(0)


def test_rolling_zscore_matches_manual_calculation() -> None:
    values = _series([1, 2, 3, 4, 10])
    result = RollingWindow(3).zscore(values)

    window = values.iloc[-3:]
    expected = (10 - window.mean()) / window.std(ddof=0)
    assert result.iloc[-1] == pytest.approx(expected)
    assert result.iloc[:2].isna().all()


def test_rolling_zscore_is_nan_on_a_flat_window() -> None:
    result = RollingWindow(3).zscore(_series([5, 5, 5, 5]))

    assert result.iloc[-1] != result.iloc[-1]  # NaN, never +/-inf


def test_rolling_zscore_of_empty_series_is_empty() -> None:
    assert RollingWindow(20).zscore(pd.Series(dtype=float)).empty


def test_rolling_beta_recovers_a_known_slope() -> None:
    x = _series([0.01, -0.02, 0.03, -0.01, 0.02, 0.005])
    y = x * 2.0

    result = RollingWindow(4).beta(y, x)

    assert result.iloc[-1] == pytest.approx(2.0)


def test_rolling_beta_is_nan_when_the_explanatory_leg_is_constant() -> None:
    x = _series([0.01] * 5)
    y = _series([0.01, 0.02, 0.03, 0.04, 0.05])

    result = RollingWindow(3).beta(y, x)

    assert result.dropna().empty


def test_rolling_correlation_of_a_perfect_match_is_one() -> None:
    x = _series([0.01, -0.02, 0.03, -0.01, 0.02])

    assert RollingWindow(4).correlation(x, x).iloc[-1] == pytest.approx(1.0)


def test_ratio_to_mean_divides_the_latest_point_by_its_average() -> None:
    assert RollingWindow(4).ratio_to_mean(_series([10, 10, 10, 20])) == pytest.approx(1.6)


@pytest.mark.parametrize(
    "values",
    [[], [0.0, 0.0, 0.0], [np.nan, np.nan]],
    ids=["empty", "zero-mean", "all-nan"],
)
def test_ratio_to_mean_returns_none_when_undefined(values: list[float]) -> None:
    assert RollingWindow(2).ratio_to_mean(_series(values)) is None


def test_ratio_to_mean_honours_min_periods() -> None:
    assert RollingWindow(30, min_periods=2).ratio_to_mean(_series([10, 20])) == pytest.approx(
        20 / 15
    )


def test_rolling_sum_and_mean_use_the_configured_window() -> None:
    values = _series([1, 2, 3, 4])

    assert RollingWindow(2).sum(values).iloc[-1] == pytest.approx(7.0)
    assert RollingWindow(2).mean(values).iloc[-1] == pytest.approx(3.5)


def test_full_sample_zscore_centres_on_the_mean() -> None:
    result = zscore(_series([1, 2, 3, 4, 5]))

    assert result.mean() == pytest.approx(0.0)
    assert result.std(ddof=0) == pytest.approx(1.0)


def test_full_sample_zscore_of_a_flat_series_is_zero() -> None:
    assert zscore(_series([7, 7, 7])).tolist() == [0.0, 0.0, 0.0]


def test_full_sample_beta_recovers_a_known_slope() -> None:
    x = _series([0.01, -0.02, 0.03, -0.01, 0.02])

    assert beta(x * 1.5, x) == pytest.approx(1.5)


def test_full_sample_beta_falls_back_when_the_explanatory_leg_is_constant() -> None:
    x = _series([0.01] * 4)

    assert beta(_series([1, 2, 3, 4]), x, default=0.7) == 0.7


def test_log_returns_drop_non_positive_prices_instead_of_returning_inf() -> None:
    result = log_returns(_series([100.0, 0.0, 110.0]))

    assert np.isfinite(result).all()


def test_log_returns_match_the_analytic_value() -> None:
    result = log_returns(_series([100.0, 110.0]))

    assert result.iloc[-1] == pytest.approx(np.log(1.1))


def test_simple_returns_match_the_analytic_value() -> None:
    assert simple_returns(_series([100.0, 110.0])).iloc[-1] == pytest.approx(0.1)


@pytest.mark.parametrize("fn", [log_returns, simple_returns], ids=["log", "simple"])
def test_returns_of_an_empty_frame_stay_empty(fn) -> None:
    assert fn(pd.DataFrame()).empty
