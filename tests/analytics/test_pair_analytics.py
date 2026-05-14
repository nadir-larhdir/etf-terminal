from __future__ import annotations

import pandas as pd

from fixed_income.etfs import ETF
from fixed_income.rv.pair_analytics import ratio, screener_snapshot
from fixed_income.rv.spread_definition import SpreadDefinition


def _history(prices: list[float], adj_prices: list[float] | None = None) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=len(prices))
    adjusted = adj_prices or prices
    frame = pd.DataFrame(index=index)
    frame["close"] = prices
    frame["adj_close"] = adjusted
    frame["open"] = prices
    frame["high"] = [p * 1.001 for p in prices]
    frame["low"] = [p * 0.999 for p in prices]
    frame["volume"] = 1_000_000.0
    return frame


def test_pair_analytics_snapshot_and_ratio() -> None:
    left = ETF("LQD", history=_history([100, 101, 102, 103, 104, 105]))
    right = ETF("IEF", history=_history([95, 95.5, 96, 96.5, 97, 97.5]))

    ratio_series = ratio(left, right)
    snapshot = screener_snapshot(SpreadDefinition("LQD", "IEF"), left, right)

    assert not ratio_series.empty
    assert snapshot.name == "LQD/IEF"
    assert isinstance(snapshot.zscore, float)
    assert isinstance(snapshot.correlation_20d, float)


def test_pair_analytics_ratio_uses_adjusted_close() -> None:
    left = ETF("LQD", history=_history([100, 100], adj_prices=[50, 60]))
    right = ETF("IEF", history=_history([100, 100], adj_prices=[25, 30]))

    ratio_series = ratio(left, right)

    assert ratio_series.tolist() == [2.0, 2.0]
