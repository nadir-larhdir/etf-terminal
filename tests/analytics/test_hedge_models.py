from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fixed_income.rv.hedge_models import (
    beta_adjusted_spread,
    beta_adjusted_zscore,
    beta_stability,
    latest_beta,
    rolling_beta,
)


def _returns(left: list[float], right: list[float]) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-01", periods=len(left))
    return pd.DataFrame({"ret_left": left, "ret_right": right}, index=index, dtype=float)


def _noise(n: int, scale: float = 0.01) -> np.ndarray:
    return np.sin(np.arange(n)) * scale


def test_rolling_beta_recovers_a_known_hedge_ratio() -> None:
    right = _noise(40)
    returns = _returns((right * 1.8).tolist(), right.tolist())

    assert rolling_beta(returns, window=20).iloc[-1] == pytest.approx(1.8)


def test_latest_beta_falls_back_when_history_is_too_short() -> None:
    returns = _returns([0.01], [0.02])

    assert latest_beta(returns, window=20, default=1.0) == 1.0


def test_latest_beta_falls_back_when_the_hedge_leg_is_constant() -> None:
    returns = _returns(_noise(40).tolist(), [0.01] * 40)

    assert latest_beta(returns, window=20, default=0.5) == 0.5


def test_beta_adjusted_spread_removes_the_hedged_leg() -> None:
    aligned = pd.DataFrame({"close_left": [100.0, 102.0], "close_right": [50.0, 51.0]})

    assert beta_adjusted_spread(aligned, beta=2.0).tolist() == [0.0, 0.0]


def test_beta_adjusted_zscore_is_standardised() -> None:
    result = beta_adjusted_zscore(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]))

    assert result.mean() == pytest.approx(0.0)
    assert result.std(ddof=0) == pytest.approx(1.0)


def test_beta_adjusted_zscore_of_a_flat_spread_is_zero() -> None:
    assert beta_adjusted_zscore(pd.Series([3.0, 3.0, 3.0])).tolist() == [0.0, 0.0, 0.0]


def test_beta_stability_is_zero_for_a_perfectly_stable_hedge() -> None:
    right = _noise(60)
    returns = _returns((right * 1.5).tolist(), right.tolist())

    assert beta_stability(returns, window=20) == pytest.approx(0.0, abs=1e-9)


def test_beta_stability_rises_when_the_hedge_ratio_drifts() -> None:
    right = _noise(60)
    drifting = np.concatenate([right[:30] * 1.0, right[30:] * 3.0])
    stable = _returns((right * 1.5).tolist(), right.tolist())
    unstable = _returns(drifting.tolist(), right.tolist())

    assert beta_stability(unstable, window=20) > beta_stability(stable, window=20)


def test_beta_stability_is_zero_without_enough_observations() -> None:
    assert beta_stability(_returns([0.01, 0.02], [0.01, 0.02]), window=20) == 0.0
