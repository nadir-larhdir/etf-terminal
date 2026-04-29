"""Regression helpers for estimating spread (credit) risk from return time series."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fixed_income.analytics.rate_models import (
    empty_model,
    ewma_weights,
    filter_outliers,
    weighted_fit,
)


def factor_beta(beta_map: dict[str, float]) -> float | None:
    """Extract the spread_change_bps coefficient from a beta map, or None if absent."""
    if "spread_change_bps" in beta_map:
        return float(beta_map["spread_change_bps"])
    return None


def regress_credit_benchmark_duration(
    frame: pd.DataFrame,
    lookback_days: int,
    benchmark_duration: float,
) -> dict[str, Any]:
    """Regress ETF returns on benchmark returns + spread changes to estimate duration and credit beta.

    Duration = benchmark_beta × benchmark_duration.
    Credit beta captures the sensitivity to OAS changes in basis points.
    """
    minimum = max(20, lookback_days // 3)
    if len(frame) < minimum:
        return empty_model(
            "Not enough observations for benchmark and spread regression.",
            len(frame),
            lookback_days,
        )

    filtered = filter_outliers(frame)
    if len(filtered) < minimum:
        return empty_model(
            "Not enough observations after outlier filtering.", len(filtered), len(filtered)
        )

    y = filtered["etf_return"].to_numpy(dtype=float)
    x = filtered.loc[:, ["benchmark_return", "spread_change_bps"]].to_numpy(dtype=float)
    weights = ewma_weights(len(filtered), lookback_days)
    design = np.column_stack([np.ones(len(filtered)), x])
    coeffs, r2 = weighted_fit(design, y, weights)
    return {
        "estimated_duration": float(coeffs[1] * benchmark_duration),
        "regression_r2": r2,
        "lookback_days_used": lookback_days,
        "observations_used": len(filtered),
        "benchmark_beta": float(coeffs[1]),
        "credit_beta": float(coeffs[2]),
        "reason": None,
    }


def regress_credit_rate_tenor_duration(
    frame: pd.DataFrame,
    lookback_days: int,
    rate_series_id: str,
) -> dict[str, Any]:
    """Regress ETF returns on a single rate tenor + spread changes to estimate duration.

    Duration = -(rate_beta) × 10,000, with spread_change_bps capturing credit sensitivity.
    """
    minimum = max(20, lookback_days // 3)
    if len(frame) < minimum:
        return empty_model(
            "Not enough observations for rate-tenor and spread regression.",
            len(frame),
            lookback_days,
        )

    filtered = filter_outliers(frame)
    if len(filtered) < minimum:
        return empty_model(
            "Not enough observations after outlier filtering.", len(filtered), len(filtered)
        )

    y = filtered["etf_return"].to_numpy(dtype=float)
    x = filtered.loc[:, [rate_series_id, "spread_change_bps"]].to_numpy(dtype=float)
    weights = ewma_weights(len(filtered), lookback_days)
    design = np.column_stack([np.ones(len(filtered)), x])
    coeffs, r2 = weighted_fit(design, y, weights)
    rate_beta = float(coeffs[1])
    return {
        "estimated_duration": float(-(rate_beta * 10_000.0)),
        "regression_r2": r2,
        "lookback_days_used": lookback_days,
        "observations_used": len(filtered),
        "benchmark_beta": rate_beta,
        "credit_beta": float(coeffs[2]),
        "reason": None,
    }
