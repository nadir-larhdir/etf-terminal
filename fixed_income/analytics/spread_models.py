from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fixed_income.analytics.rate_models import empty_model, ewma_weights, filter_outliers, weighted_fit


def factor_beta(beta_map: dict[str, float]) -> float | None:
    if "spread_change_bps" in beta_map:
        return float(beta_map["spread_change_bps"])
    return None


def regress_credit_benchmark_duration(
    frame: pd.DataFrame,
    lookback_days: int,
    benchmark_duration: float,
) -> dict[str, Any]:
    minimum = max(20, lookback_days // 3)
    if len(frame) < minimum:
        return empty_model("Not enough observations for benchmark and spread regression.", len(frame), lookback_days)

    filtered = filter_outliers(frame)
    if len(filtered) < minimum:
        return empty_model("Not enough observations after outlier filtering.", len(filtered), len(filtered))

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
        "credit_beta": float(coeffs[2]),
        "reason": None,
    }
