"""Helpers for loading and transforming spread factor data used in regressions."""

from __future__ import annotations

import pandas as pd


def spread_changes_bps(macro_store, series_id: str, *, start_date: str) -> pd.Series:
    """Return a date-indexed Series of daily OAS spread changes in basis points for one series."""
    matrix = macro_store.get_series_matrix([series_id], start_date=start_date)
    if matrix.empty or series_id not in matrix.columns:
        return pd.Series(dtype=float)
    return matrix[series_id].astype(float).diff().mul(100.0).dropna().rename("spread_change_bps")
