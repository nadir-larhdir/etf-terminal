from __future__ import annotations

import pandas as pd


def rolling_beta(returns: pd.DataFrame, window: int = 20) -> pd.Series:
    cov = returns["ret_left"].rolling(window).cov(returns["ret_right"])
    var = returns["ret_right"].rolling(window).var()
    return (cov / var).replace([float("inf"), float("-inf")], pd.NA)


def latest_beta(returns: pd.DataFrame, window: int = 20, default: float = 1.0) -> float:
    beta_series = rolling_beta(returns, window=window).dropna()
    if beta_series.empty:
        return default
    return float(beta_series.iloc[-1])


def beta_adjusted_spread(aligned: pd.DataFrame, beta: float) -> pd.Series:
    return aligned["close_left"] - beta * aligned["close_right"]


def beta_adjusted_zscore(spread: pd.Series) -> pd.Series:
    if spread.empty:
        return pd.Series(dtype=float)
    mean_val = spread.mean()
    std_val = spread.std(ddof=0)
    if pd.isna(std_val) or float(std_val) == 0:
        return pd.Series(0.0, index=spread.index)
    return (spread - mean_val) / std_val


def beta_stability(returns: pd.DataFrame, window: int = 20) -> float:
    beta_series = rolling_beta(returns, window=window).dropna()
    if len(beta_series) <= 1:
        return 0.0
    return float(beta_series.std(ddof=0))
