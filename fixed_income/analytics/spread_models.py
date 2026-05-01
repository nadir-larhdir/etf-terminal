"""Regression helpers for estimating spread sensitivity from return time series."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fixed_income.config.model_settings import EWMA_ALPHA


def ewma_blend(values: list[float | None], alpha: float = EWMA_ALPHA) -> float | None:
    """Return the EWMA of scalar values, or None if all values are missing."""
    valid = [v for v in values if v is not None and not pd.isna(v)]
    if not valid:
        return None
    return float(pd.Series(valid, dtype=float).ewm(alpha=alpha, adjust=False).mean().iloc[-1])


def _ewma_weights(length: int, lookback_days: int) -> np.ndarray:
    half_life = max(10.0, lookback_days / 3.0)
    ages = np.arange(length - 1, -1, -1, dtype=float)
    return np.power(0.5, ages / half_life)


def _filter_outliers(frame: pd.DataFrame) -> pd.DataFrame:
    lower = frame["etf_return"].quantile(0.01)
    upper = frame["etf_return"].quantile(0.99)
    return frame.loc[frame["etf_return"].between(lower, upper)].copy()


def _weighted_fit(
    design: np.ndarray, y: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, float | None]:
    sqrt_w = np.sqrt(weights)
    coeffs = np.linalg.lstsq(design * sqrt_w[:, None], y * sqrt_w, rcond=None)[0]
    fitted = design @ coeffs
    weighted_mean = float(np.average(y, weights=weights))
    total = float(np.sum(weights * (y - weighted_mean) ** 2))
    residual = float(np.sum(weights * (y - fitted) ** 2))
    r2 = None if total <= 0 else max(0.0, 1.0 - residual / total)
    return coeffs, None if r2 is None else float(r2)


def empty_spread_model(
    reason: str,
    observations_used: int | None = None,
    lookback_days_used: int | None = None,
) -> dict[str, Any]:
    return {
        "credit_beta": None,
        "regression_r2": None,
        "lookback_days_used": lookback_days_used,
        "observations_used": observations_used,
        "reason": reason,
    }


def regress_spread_beta(frame: pd.DataFrame, lookback_days: int) -> dict[str, Any]:
    """Regress ETF returns on OAS changes to estimate spread sensitivity per bp."""
    minimum = max(20, lookback_days // 3)
    if len(frame) < minimum:
        return empty_spread_model(
            "Not enough observations for spread regression.", len(frame), lookback_days
        )

    filtered = _filter_outliers(frame)
    if len(filtered) < minimum:
        return empty_spread_model(
            "Not enough observations after outlier filtering.", len(filtered), len(filtered)
        )

    y = filtered["etf_return"].to_numpy(dtype=float)
    x = filtered["spread_change_bps"].to_numpy(dtype=float)
    weights = _ewma_weights(len(filtered), lookback_days)
    design = np.column_stack([np.ones(len(filtered)), x])
    coeffs, r2 = _weighted_fit(design, y, weights)
    return {
        "credit_beta": float(coeffs[1]),
        "regression_r2": r2,
        "lookback_days_used": lookback_days,
        "observations_used": len(filtered),
        "reason": None,
    }
