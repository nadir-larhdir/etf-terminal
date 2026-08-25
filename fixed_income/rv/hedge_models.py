"""Beta estimation and spread construction for relative-value ETF pairs."""

from __future__ import annotations

import pandas as pd

from fixed_income import series

DEFAULT_HEDGE_WINDOW = 20


def rolling_beta(returns: pd.DataFrame, window: int = DEFAULT_HEDGE_WINDOW) -> pd.Series:
    """Return the rolling OLS beta of ret_left on ret_right over the given window."""
    return series.RollingWindow(window).beta(returns["ret_left"], returns["ret_right"])


def latest_beta(
    returns: pd.DataFrame, window: int = DEFAULT_HEDGE_WINDOW, default: float = 1.0
) -> float:
    """Return the most recent rolling beta, falling back to default if not enough data."""
    estimates = rolling_beta(returns, window=window).dropna()
    return default if estimates.empty else float(estimates.iloc[-1])


def beta_adjusted_spread(aligned: pd.DataFrame, beta: float) -> pd.Series:
    """Return the beta-adjusted price spread: left_price - beta * right_price."""
    return aligned["close_left"] - beta * aligned["close_right"]


def beta_adjusted_zscore(spread: pd.Series) -> pd.Series:
    """Return the full-sample z-score of a spread series; flat spreads score 0.0."""
    return series.zscore(spread)


def beta_stability(returns: pd.DataFrame, window: int = DEFAULT_HEDGE_WINDOW) -> float:
    """Return the dispersion of the rolling beta; lower means a more stable hedge ratio."""
    estimates = rolling_beta(returns, window=window).dropna()
    return 0.0 if len(estimates) <= 1 else float(estimates.std(ddof=0))
