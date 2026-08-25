from __future__ import annotations

import numpy as np
import pandas as pd

from fixed_income.analytics import FixedIncomeAnalyticsService, RiskProxySelector
from fixed_income.etfs import ETF
from tests.fakes import FakeMacroStore, FakePriceStore


def _price_history_from_returns(returns: np.ndarray, *, start_price: float = 100.0) -> pd.DataFrame:
    index = pd.bdate_range("2024-01-02", periods=len(returns))
    prices = start_price * np.exp(np.cumsum(returns))
    frame = pd.DataFrame(index=index)
    frame["close"] = prices
    frame["adj_close"] = prices
    frame["open"] = prices
    frame["high"] = prices * 1.001
    frame["low"] = prices * 0.999
    frame["volume"] = 1_000_000.0
    return frame


def _synthetic_environment() -> tuple[FakePriceStore, FakeMacroStore]:
    rng = np.random.default_rng(7)
    periods = 220
    index = pd.bdate_range("2024-01-02", periods=periods)

    dgs3mo = rng.normal(0.0, 4.5, periods)
    dgs6mo = rng.normal(0.0, 4.2, periods)
    dgs1 = rng.normal(0.0, 4.1, periods)
    dgs2 = rng.normal(0.0, 4.0, periods)
    dgs3 = rng.normal(0.0, 3.8, periods)
    dgs5 = rng.normal(0.0, 3.0, periods)
    dgs7 = rng.normal(0.0, 2.8, periods)
    dgs10 = rng.normal(0.0, 2.5, periods)
    dgs20 = rng.normal(0.0, 2.2, periods)
    dgs30 = rng.normal(0.0, 2.0, periods)

    shy_returns = -(1.8 / 10000.0) * (
        0.20 * dgs3mo
        + 0.15 * dgs6mo
        + 0.15 * dgs1
        + 0.25 * dgs2
        + 0.10 * dgs3
        + 0.07 * dgs5
        + 0.04 * dgs7
        + 0.02 * dgs10
        + 0.01 * dgs20
        + 0.01 * dgs30
    )
    ief_returns = -(7.5 / 10000.0) * (
        0.03 * dgs3mo
        + 0.04 * dgs6mo
        + 0.05 * dgs1
        + 0.10 * dgs2
        + 0.10 * dgs3
        + 0.18 * dgs5
        + 0.15 * dgs7
        + 0.18 * dgs10
        + 0.10 * dgs20
        + 0.07 * dgs30
    )
    tlt_returns = -(16.0 / 10000.0) * (
        0.01 * dgs3mo
        + 0.01 * dgs6mo
        + 0.02 * dgs1
        + 0.03 * dgs2
        + 0.04 * dgs3
        + 0.08 * dgs5
        + 0.10 * dgs7
        + 0.18 * dgs10
        + 0.23 * dgs20
        + 0.30 * dgs30
    )

    ig_spread_bps = rng.normal(0.0, 1.0, periods)
    hy_spread_bps = rng.normal(0.0, 1.2, periods)

    lqd_returns = 1.05 * ief_returns - 0.0008 * ig_spread_bps
    hyg_returns = 1.85 * shy_returns - 0.0002 * hy_spread_bps

    macro_matrix = pd.DataFrame(
        {
            "DGS3MO": 4.60 + np.cumsum(dgs3mo) / 100.0,
            "DGS6MO": 4.50 + np.cumsum(dgs6mo) / 100.0,
            "DGS1": 4.45 + np.cumsum(dgs1) / 100.0,
            "DGS2": 4.40 + np.cumsum(dgs2) / 100.0,
            "DGS3": 4.25 + np.cumsum(dgs3) / 100.0,
            "DGS5": 4.10 + np.cumsum(dgs5) / 100.0,
            "DGS7": 4.05 + np.cumsum(dgs7) / 100.0,
            "DGS10": 4.00 + np.cumsum(dgs10) / 100.0,
            "DGS20": 4.10 + np.cumsum(dgs20) / 100.0,
            "DGS30": 4.20 + np.cumsum(dgs30) / 100.0,
            "BAMLC0A0CM": 1.20 + np.cumsum(ig_spread_bps) / 100.0,
            "BAMLH0A0HYM2": 3.90 + np.cumsum(hy_spread_bps) / 100.0,
        },
        index=index,
    )

    price_store = FakePriceStore(
        {
            "SHY": _price_history_from_returns(shy_returns, start_price=82.0),
            "IEF": _price_history_from_returns(ief_returns, start_price=94.0),
            "TLT": _price_history_from_returns(tlt_returns, start_price=88.0),
            "LQD": _price_history_from_returns(lqd_returns, start_price=106.0),
            "HYG": _price_history_from_returns(hyg_returns, start_price=78.0),
        }
    )
    return price_store, FakeMacroStore(macro_matrix)


def test_fixed_income_analytics_service_smoke_estimates() -> None:
    price_store, macro_store = _synthetic_environment()
    service = FixedIncomeAnalyticsService(price_store, macro_store, RiskProxySelector())

    tlt = ETF(
        "TLT",
        name="Treasury ETF",
        asset_class="UST Long",
        history=price_store.get_ticker_price_history("TLT"),
        metadata={"duration": 15.3},
    )
    ief = ETF(
        "IEF",
        name="Treasury ETF",
        asset_class="UST Belly",
        history=price_store.get_ticker_price_history("IEF"),
        metadata={"duration": 6.9},
    )
    lqd = ETF(
        "LQD",
        name="Investment Grade Bond ETF",
        asset_class="IG Credit",
        history=price_store.get_ticker_price_history("LQD"),
        metadata={"duration": 7.9},
    )
    hyg = ETF(
        "HYG",
        name="High Yield Bond ETF",
        asset_class="HY Credit",
        history=price_store.get_ticker_price_history("HYG"),
        metadata={"duration": 3.0},
    )

    tlt_result = service.analyze_etf(tlt)
    ief_result = service.analyze_etf(ief)
    lqd_result = service.analyze_etf(lqd)
    hyg_result = service.analyze_etf(hyg)

    assert tlt_result.model_type_used == "provider_metadata"
    assert tlt_result.estimated_duration == 15.3

    assert ief_result.estimated_duration == 6.9

    assert lqd_result.spread_proxy_used == "BAMLC0A0CM"
    assert lqd_result.estimated_duration == 7.9

    assert hyg_result.spread_proxy_used == "BAMLH0A0HYM2"
    assert hyg_result.estimated_duration == 3.0
    assert (hyg_result.spread_beta_per_bp or 0.0) < 0.0


def test_fixed_income_analytics_service_prefers_metadata_duration() -> None:
    price_store, macro_store = _synthetic_environment()
    service = FixedIncomeAnalyticsService(price_store, macro_store, RiskProxySelector())

    lqd = ETF(
        "LQD",
        name="Investment Grade Bond ETF",
        asset_class="IG Credit",
        history=price_store.get_ticker_price_history("LQD"),
        metadata={"duration": 8.0},
    )

    result = service.analyze_etf(lqd)

    assert result.estimated_duration == 8.0
    assert result.dv01_per_share is not None
