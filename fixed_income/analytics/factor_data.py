from __future__ import annotations

import pandas as pd

from fixed_income.config.model_settings import RATE_SERIES


def treasury_rate_changes_bps(macro_store, *, start_date: str) -> pd.DataFrame:
    rates = macro_store.get_series_matrix(list(RATE_SERIES), start_date=start_date)
    if rates.empty:
        return pd.DataFrame()
    return rates.loc[:, list(RATE_SERIES)].astype(float).diff().mul(100.0).dropna()


def spread_changes_bps(macro_store, series_id: str, *, start_date: str) -> pd.Series:
    matrix = macro_store.get_series_matrix([series_id], start_date=start_date)
    if matrix.empty or series_id not in matrix.columns:
        return pd.Series(dtype=float)
    return matrix[series_id].astype(float).diff().mul(100.0).dropna().rename("spread_change_bps")
