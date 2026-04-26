"""Regression helpers for estimating rate duration from return time series."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fixed_income.config.model_settings import EWMA_ALPHA, MIN_OBSERVATIONS, RATE_SERIES


def ewma_blend(values: list[float | None], alpha: float = EWMA_ALPHA) -> float | None:
    """Return the EWMA of a list of scalar values, or None if all are missing."""
    valid = [v for v in values if v is not None and not pd.isna(v)]
    if not valid:
        return None
    return float(pd.Series(valid, dtype=float).ewm(alpha=alpha, adjust=False).mean().iloc[-1])


def ewma_weights(length: int, lookback_days: int) -> np.ndarray:
    """Return an array of exponential decay weights with half-life tied to lookback_days."""
    half_life = max(10.0, lookback_days / 3.0)
    ages = np.arange(length - 1, -1, -1, dtype=float)
    return np.power(0.5, ages / half_life)


def filter_outliers(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove rows where etf_return falls outside the 1st–99th percentile range."""
    lower = frame["etf_return"].quantile(0.01)
    upper = frame["etf_return"].quantile(0.99)
    return frame.loc[frame["etf_return"].between(lower, upper)].copy()


def weighted_fit(
    design: np.ndarray, y: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, float | None]:
    """Run weighted least-squares and return (coefficients, weighted R²).

    Returns R² of None when the total weighted variance is zero (constant target).
    """
    sqrt_w = np.sqrt(weights)
    coeffs = np.linalg.lstsq(design * sqrt_w[:, None], y * sqrt_w, rcond=None)[0]
    fitted = design @ coeffs
    weighted_mean = float(np.average(y, weights=weights))
    total = float(np.sum(weights * (y - weighted_mean) ** 2))
    residual = float(np.sum(weights * (y - fitted) ** 2))
    r2 = None if total <= 0 else max(0.0, 1.0 - residual / total)
    return coeffs, None if r2 is None else float(r2)


def empty_model(
    reason: str,
    observations_used: int | None = None,
    lookback_days_used: int | None = None,
) -> dict[str, Any]:
    """Return a null-filled result dict used when a regression cannot be run."""
    return {
        "estimated_duration": None,
        "regression_r2": None,
        "lookback_days_used": lookback_days_used,
        "observations_used": observations_used,
        "benchmark_beta": None,
        "credit_beta": None,
        "reason": reason,
    }


def regress_duration(
    frame: pd.DataFrame, lookback_days: int, factor_columns: list[str]
) -> dict[str, Any]:
    """Estimate duration by regressing ETF returns on rate-change factors.

    Duration is derived as -(sum of rate betas) × 10,000, converting from
    return-per-bp to years of duration.
    """
    minimum = max(MIN_OBSERVATIONS, lookback_days // 3)
    if len(frame) < minimum:
        return empty_model("Not enough observations for regression.", len(frame), lookback_days)

    filtered = filter_outliers(frame)
    if len(filtered) < minimum:
        return empty_model("Not enough observations after outlier filtering.", len(filtered), len(filtered))

    y = filtered["etf_return"].to_numpy(dtype=float)
    x = filtered.loc[:, factor_columns].to_numpy(dtype=float)
    weights = ewma_weights(len(filtered), lookback_days)
    design = np.column_stack([np.ones(len(filtered)), x])
    coeffs, r2 = weighted_fit(design, y, weights)
    beta_map = dict(zip(factor_columns, coeffs[1:], strict=False))
    rate_beta_sum = sum(float(beta_map.get(s, 0.0)) for s in RATE_SERIES)
    return {
        "estimated_duration": float(-(rate_beta_sum * 10_000.0)),
        "regression_r2": r2,
        "lookback_days_used": lookback_days,
        "observations_used": len(filtered),
        "benchmark_beta": None,
        "credit_beta": None,
        "reason": None,
    }


def regress_benchmark_duration(
    frame: pd.DataFrame, lookback_days: int, benchmark_duration: float
) -> dict[str, Any]:
    """Estimate duration by regressing ETF returns on a single benchmark return series.

    Duration = beta × benchmark_duration, using the ETF's sensitivity to the benchmark.
    """
    minimum = max(MIN_OBSERVATIONS, lookback_days // 3)
    if len(frame) < minimum:
        return empty_model("Not enough observations for benchmark regression.", len(frame), lookback_days)

    filtered = filter_outliers(frame)
    if len(filtered) < minimum:
        return empty_model("Not enough observations after outlier filtering.", len(filtered), len(filtered))

    y = filtered["etf_return"].to_numpy(dtype=float)
    x = filtered["benchmark_return"].to_numpy(dtype=float)
    weights = ewma_weights(len(filtered), lookback_days)
    design = np.column_stack([np.ones(len(filtered)), x])
    coeffs, r2 = weighted_fit(design, y, weights)
    return {
        "estimated_duration": float(coeffs[1] * benchmark_duration),
        "regression_r2": r2,
        "lookback_days_used": lookback_days,
        "observations_used": len(filtered),
        "benchmark_beta": float(coeffs[1]),
        "credit_beta": None,
        "reason": None,
    }
