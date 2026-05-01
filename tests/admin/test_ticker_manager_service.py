from __future__ import annotations

from services.admin.ticker_manager_service import TickerManagerService


class FakeFMPClient:
    def get_security_profile(self, ticker: str) -> dict:
        return {
            "type": "ETF",
            "companyName": f"{ticker} Corporate Bond ETF",
            "category": "Investment Grade",
            "description": "Fixed income corporate credit exposure.",
        }


class FakeStore:
    def __init__(self) -> None:
        self.rows = []
        self.deleted: list[str] = []

    def upsert_etfs(self, rows, update_existing: bool = True) -> None:
        self.rows.extend(rows)

    def upsert_metadata(self, rows) -> None:
        self.rows.extend(rows)

    def delete_ticker(self, ticker: str) -> None:
        self.deleted.append(ticker)


class FakeMarketDataService:
    def __init__(self) -> None:
        self.synced: list[tuple[list[str], str, bool]] = []

    def sync_price_history(
        self, tickers: list[str], period: str = "1y", replace_existing: bool = True
    ) -> None:
        self.synced.append((tickers, period, replace_existing))


def test_ticker_manager_uses_injected_metadata_builder_for_add() -> None:
    etf_universe_store = FakeStore()
    metadata_store = FakeStore()
    market_data_service = FakeMarketDataService()
    manager = TickerManagerService(
        etf_universe_store=etf_universe_store,
        price_store=FakeStore(),
        metadata_store=metadata_store,
        market_data_service=market_data_service,
        metadata_builder=lambda ticker: {
            "ticker": ticker,
            "long_name": "Test Investment Grade Corporate Bond ETF",
            "category": "Investment Grade",
            "description": "Corporate bond fund.",
        },
    )
    manager.fmp_client = FakeFMPClient()

    profile = manager.add_ticker(" test ", period="30d")

    assert profile.ticker == "TEST"
    assert profile.asset_class == "IG Credit"
    assert etf_universe_store.rows[0]["ticker"] == "TEST"
    assert metadata_store.rows[0]["ticker"] == "TEST"
    assert market_data_service.synced == [(["TEST"], "30d", False)]
