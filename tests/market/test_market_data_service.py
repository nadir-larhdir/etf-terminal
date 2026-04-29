from __future__ import annotations

from services.market.market_data_service import MarketDataService


class FakePriceStore:
    pass


def test_market_data_service_normalizes_tickers_once_in_order() -> None:
    service = MarketDataService(FakePriceStore())

    assert service._normalise_tickers([" ief", "HYG", "ief", "", " tlt "]) == [
        "IEF",
        "HYG",
        "TLT",
    ]
