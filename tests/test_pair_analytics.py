from __future__ import annotations

import pandas as pd

from fixed_income.instruments.security import Security
from fixed_income.rv.pair_analytics import ratio, screener_snapshot
from fixed_income.rv.spread_definition import SpreadDefinition


def _history(prices: list[float]) -> pd.DataFrame:
    index = pd.bdate_range("2025-01-02", periods=len(prices))
    frame = pd.DataFrame(index=index)
    frame["close"] = prices
    frame["adj_close"] = prices
    frame["open"] = prices
    frame["high"] = [p * 1.001 for p in prices]
    frame["low"] = [p * 0.999 for p in prices]
    frame["volume"] = 1_000_000.0
    return frame


def test_pair_analytics_snapshot_and_ratio() -> None:
    left = Security("LQD", history=_history([100, 101, 102, 103, 104, 105]))
    right = Security("IEF", history=_history([95, 95.5, 96, 96.5, 97, 97.5]))

    ratio_series = ratio(left, right)
    snapshot = screener_snapshot(SpreadDefinition("LQD", "IEF"), left, right)

    assert not ratio_series.empty
    assert snapshot.name == "LQD/IEF"
    assert isinstance(snapshot.zscore, float)
    assert isinstance(snapshot.correlation_20d, float)
