"""Statistical helpers for relative-value beta estimation and spread analysis."""

from __future__ import annotations

import pandas as pd


def rolling_beta(returns: pd.DataFrame, window: int = 20) -> pd.Series:
    """Return the rolling OLS beta of ret_left on ret_right over the given window.

    Infinite values (zero variance in the right leg) are replaced with NaN.
    """
    cov = returns["ret_left"].rolling(window).cov(returns["ret_right"])
    var = returns["ret_right"].rolling(window).var()
    return (cov / var).replace([float("inf"), float("-inf")], pd.NA)


def latest_beta(returns: pd.DataFrame, window: int = 20, default: float = 1.0) -> float:
    """Return the most recent rolling beta, falling back to default if not enough data."""
    series = rolling_beta(returns, window=window).dropna()
    if series.empty:
        return default
    return float(series.iloc[-1])


def beta_adjusted_spread(aligned: pd.DataFrame, beta: float) -> pd.Series:
    """Return the beta-adjusted price spread: left_price - beta * right_price."""
    return aligned["close_left"] - beta * aligned["close_right"]


def beta_adjusted_zscore(spread: pd.Series) -> pd.Series:
    """Return the full-sample z-score of a spread series.

    Returns a zero series when the spread has zero standard deviation.
    """
    if spread.empty:
        return pd.Series(dtype=float)
    mean_val = spread.mean()
    std_val = spread.std(ddof=0)
    if pd.isna(std_val) or float(std_val) == 0:
        return pd.Series(0.0, index=spread.index)
    return (spread - mean_val) / std_val


def beta_stability(returns: pd.DataFrame, window: int = 20) -> float:
    """Return the standard deviation of the rolling beta series as a stability measure.

    A lower value indicates a more stable hedge ratio over time.
    """
    series = rolling_beta(returns, window=window).dropna()
    if len(series) <= 1:
        return 0.0
    return float(series.std(ddof=0))
