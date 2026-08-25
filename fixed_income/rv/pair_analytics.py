"""Pair-level relative-value analytics: aligned prices, ratio z-scores, and screener rows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import pandas as pd

from fixed_income import series as ts
from fixed_income.rv.hedge_models import (
    beta_adjusted_spread,
    beta_adjusted_zscore,
    beta_stability,
    latest_beta,
)
from fixed_income.rv.spread_definition import RVAnalyticsSnapshot, SpreadDefinition

if TYPE_CHECKING:
    from fixed_income.etfs import ETF
    from stores.protocols import DateLike

CORRELATION_WINDOW = 20
TARGET_HALF_LIFE_DAYS = 10.0
HALF_LIFE_TOLERANCE_DAYS = 20.0


def aligned_prices(left: ETF, right: ETF) -> pd.DataFrame:
    """Return the two legs' adjusted closes on their common trading days."""
    left_close = left.adj_close_series().rename("close_left")
    right_close = right.adj_close_series().rename("close_right")
    if left_close.empty or right_close.empty:
        return pd.DataFrame(columns=["close_left", "close_right"])
    return pd.concat([left_close, right_close], axis=1).dropna()


def filtered_prices(
    left: ETF, right: ETF, *, start_date: DateLike = None, end_date: DateLike = None
) -> pd.DataFrame:
    """Return aligned prices restricted to an optional inclusive date range."""
    prices = aligned_prices(left, right)
    if prices.empty:
        return prices
    dates = pd.to_datetime(prices.index)
    mask = pd.Series(True, index=prices.index)
    if start_date is not None:
        mask &= dates >= pd.Timestamp(start_date)
    if end_date is not None:
        mask &= dates <= pd.Timestamp(end_date)
    return prices.loc[mask]


def returns_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Return aligned simple returns for a two-column price frame."""
    if prices.empty:
        return pd.DataFrame(columns=["ret_left", "ret_right"])
    returns = ts.simple_returns(prices)
    return returns.rename(columns={"close_left": "ret_left", "close_right": "ret_right"})


def returns_frame(left: ETF, right: ETF) -> pd.DataFrame:
    """Return both legs' simple returns on their common trading days."""
    left_returns = left.returns().rename("ret_left")
    right_returns = right.returns().rename("ret_right")
    if left_returns.empty or right_returns.empty:
        return pd.DataFrame(columns=["ret_left", "ret_right"])
    return pd.concat([left_returns, right_returns], axis=1).dropna()


def ratio(
    left: ETF, right: ETF, *, start_date: DateLike = None, end_date: DateLike = None
) -> pd.Series:
    """Return the price ratio of the left leg over the right leg."""
    prices = filtered_prices(left, right, start_date=start_date, end_date=end_date)
    if prices.empty:
        return ts.EMPTY
    return prices["close_left"] / prices["close_right"]


def rolling_correlation(left: ETF, right: ETF, *, window: int = CORRELATION_WINDOW) -> pd.Series:
    """Return the rolling return correlation between the two legs."""
    merged = returns_frame(left, right)
    if merged.empty:
        return ts.EMPTY
    return ts.RollingWindow(window).correlation(merged["ret_left"], merged["ret_right"])


def half_life_from_autocorr(lag1_autocorr: float | None) -> float | None:
    """Convert a lag-1 autocorrelation into an OU half-life in days, when mean-reverting."""
    if lag1_autocorr is None or not 0 < lag1_autocorr < 1:
        return None
    return -math.log(2) / math.log(lag1_autocorr)


@dataclass(frozen=True)
class StabilityScore:
    """A 0-100 tradability score blending co-movement, mean reversion, and hedge stability.

    Each component is clamped to [0, 1] before weighting, so the score is bounded and a
    single degenerate input cannot dominate.
    """

    correlation: float
    half_life_days: float | None
    beta_dispersion: float

    WEIGHTS: ClassVar[dict[str, float]] = {"correlation": 0.45, "half_life": 0.30, "beta": 0.25}

    @classmethod
    def from_pair(cls, prices: pd.DataFrame, returns: pd.DataFrame) -> StabilityScore:
        """Build the score inputs from one pair's aligned prices and returns."""
        spread_ratio = (
            prices["close_left"] / prices["close_right"] if not prices.empty else ts.EMPTY
        )
        correlations = (
            ts.RollingWindow(CORRELATION_WINDOW)
            .correlation(returns["ret_left"], returns["ret_right"])
            .dropna()
            if not returns.empty
            else ts.EMPTY
        )
        autocorr = float(spread_ratio.autocorr(lag=1)) if len(spread_ratio) > 3 else None
        return cls(
            correlation=float(correlations.iloc[-1]) if not correlations.empty else 0.0,
            half_life_days=half_life_from_autocorr(autocorr),
            beta_dispersion=(
                0.0 if returns.empty else beta_stability(returns, window=CORRELATION_WINDOW)
            ),
        )

    @property
    def value(self) -> float:
        """Return the weighted 0-100 score."""
        components = {
            "correlation": abs(self.correlation),
            "half_life": self._half_life_component(),
            "beta": 1.0 / (1.0 + self.beta_dispersion),
        }
        return 100.0 * sum(self.WEIGHTS[key] * _clamp(value) for key, value in components.items())

    def _half_life_component(self) -> float:
        """Score peaks at TARGET_HALF_LIFE_DAYS and decays linearly either side of it."""
        if self.half_life_days is None:
            return 0.0
        distance = abs(self.half_life_days - TARGET_HALF_LIFE_DAYS)
        return 1.0 - distance / HALF_LIFE_TOLERANCE_DAYS


def screener_snapshot(
    definition: SpreadDefinition,
    left: ETF,
    right: ETF,
    *,
    start_date: DateLike = None,
    end_date: DateLike = None,
    prices: pd.DataFrame | None = None,
) -> RVAnalyticsSnapshot:
    """Return the one-row screener summary for a pair: z-score, correlation, and stability."""
    if prices is None:
        prices = filtered_prices(left, right, start_date=start_date, end_date=end_date)
    if prices.empty:
        return RVAnalyticsSnapshot(
            name=definition.name, zscore=0.0, correlation_20d=0.0, stability=0.0
        )

    spread_ratio = prices["close_left"] / prices["close_right"]
    returns = returns_from_prices(prices)
    score = StabilityScore.from_pair(prices, returns)
    latest_zscore = float(ts.zscore(spread_ratio).iloc[-1]) if len(spread_ratio) > 1 else 0.0
    return RVAnalyticsSnapshot(
        name=definition.name,
        zscore=round(latest_zscore, 2),
        correlation_20d=round(score.correlation, 2),
        stability=round(score.value, 0),
    )


def beta_metrics(
    left: ETF,
    right: ETF,
    *,
    start_date: DateLike = None,
    end_date: DateLike = None,
    beta: float | None = None,
) -> tuple[float, pd.Series, pd.Series]:
    """Return the hedge beta with its beta-adjusted spread and that spread's z-score."""
    aligned = filtered_prices(left, right, start_date=start_date, end_date=end_date)
    returns = returns_frame(left, right)
    beta_value = beta if beta is not None else latest_beta(returns)
    if aligned.empty:
        return beta_value, ts.EMPTY, ts.EMPTY
    spread = beta_adjusted_spread(aligned, beta=beta_value)
    return beta_value, spread, beta_adjusted_zscore(spread)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
