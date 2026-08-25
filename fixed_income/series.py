"""Rolling and full-sample time-series primitives shared by analytics, RV, and macro code.

`RollingWindow` carries the lookback as state so a call site names its window once
(`Z60 = RollingWindow(60)`) and reuses it. Every estimator returns NaN rather than an
infinity when the denominator collapses, so downstream `dropna()` is always sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.core.window import Rolling

EMPTY = pd.Series(dtype=float)


@dataclass(frozen=True)
class RollingWindow:
    """A named rolling lookback exposing the estimators computed over it."""

    window: int
    min_periods: int | None = None

    def __post_init__(self) -> None:
        if self.window < 1:
            raise ValueError(f"window must be >= 1, got {self.window}")

    def mean(self, series: pd.Series) -> pd.Series:
        return self._roll(series).mean()

    def std(self, series: pd.Series) -> pd.Series:
        """Population standard deviation (ddof=0), matching the z-score convention."""
        return self._roll(series).std(ddof=0)

    def sum(self, series: pd.Series) -> pd.Series:
        return self._roll(series).sum()

    def zscore(self, series: pd.Series) -> pd.Series:
        """Rolling z-score; NaN where the rolling standard deviation is zero."""
        if series.empty:
            return EMPTY
        return (series - self.mean(series)) / _no_zero(self.std(series))

    def beta(self, y: pd.Series, x: pd.Series) -> pd.Series:
        """Rolling OLS beta of y on x (cov/var); NaN where x has zero variance."""
        if y.empty or x.empty:
            return EMPTY
        return self._roll(y).cov(x) / _no_zero(self._roll(x).var())

    def correlation(self, y: pd.Series, x: pd.Series) -> pd.Series:
        if y.empty or x.empty:
            return EMPTY
        return self._roll(y).corr(x)

    def ratio_to_mean(self, series: pd.Series) -> float | None:
        """Latest observation divided by its rolling mean, or None when undefined."""
        if series.empty:
            return None
        average = self.mean(series).iloc[-1]
        latest = series.iloc[-1]
        if pd.isna(latest) or pd.isna(average) or average == 0:
            return None
        return float(latest / average)

    def _roll(self, series: pd.Series) -> Rolling:
        return series.rolling(self.window, min_periods=self.min_periods)


def zscore(series: pd.Series) -> pd.Series:
    """Full-sample z-score; a zero-variance series scores flat at 0.0."""
    if series.empty:
        return EMPTY
    deviation = series.std(ddof=0)
    if pd.isna(deviation) or float(deviation) == 0:
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / deviation


def beta(y: pd.Series, x: pd.Series, *, default: float = 1.0) -> float:
    """Full-sample OLS beta of y on x, falling back to default when x has no variance."""
    variance = x.var()
    if pd.isna(variance) or float(variance) == 0:
        return default
    estimate = y.cov(x)
    return default if pd.isna(estimate) else float(estimate / variance)


def log_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """Daily log returns; non-positive prices are dropped rather than yielding -inf."""
    if prices.empty:
        return prices.iloc[:0].astype(float)
    return np.log(prices.where(prices > 0)).diff().dropna()


def simple_returns(prices: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    if prices.empty:
        return prices.iloc[:0].astype(float)
    return prices.pct_change().dropna()


def _no_zero(series: pd.Series) -> pd.Series:
    """Map zeros and infinities to NaN so downstream division degrades to NaN."""
    return series.replace([0, np.inf, -np.inf], np.nan)


VOLUME_WINDOW = RollingWindow(30, min_periods=5)


def volume_multiple(history: pd.DataFrame, column: str = "volume") -> float | None:
    """Latest traded volume as a multiple of its 30-day average, or None when unavailable."""
    if history is None or history.empty or column not in history.columns:
        return None
    return VOLUME_WINDOW.ratio_to_mean(history[column].astype(float))
