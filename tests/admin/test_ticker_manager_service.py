from __future__ import annotations

from services.admin.ticker_manager_service import TickerManagerService
from tests.fakes import FakeMetadataStore, FakePriceStore, FakePriceSyncer, FakeUniverseStore


class FakeFMPClient:
    def get_security_profile(self, ticker: str) -> dict[str, str]:
        return {
            "type": "ETF",
            "companyName": f"{ticker} Corporate Bond ETF",
            "category": "Investment Grade",
            "description": "Fixed income corporate credit exposure.",
        }


def test_ticker_manager_uses_injected_metadata_builder_for_add() -> None:
    etf_universe_store = FakeUniverseStore()
    metadata_store = FakeMetadataStore()
    market_data_service = FakePriceSyncer()
    manager = TickerManagerService(
        etf_universe_store=etf_universe_store,
        price_store=FakePriceStore(),
        metadata_store=metadata_store,
        market_data_service=market_data_service,
        metadata_builder=lambda ticker: {
            "ticker": ticker,
            "long_name": "Test Investment Grade Corporate Bond ETF",
            "category": "Investment Grade",
            "description": "Corporate bond fund.",
        },
    )
    manager.fmp_client = FakeFMPClient()  # type: ignore[assignment]

    profile = manager.add_ticker(" test ", period="30d")

    assert profile.ticker == "TEST"
    assert profile.asset_class == "IG Credit"
    assert etf_universe_store.rows[0]["ticker"] == "TEST"
    assert metadata_store.rows[0]["ticker"] == "TEST"
    assert market_data_service.synced == [(["TEST"], "30d", False)]
