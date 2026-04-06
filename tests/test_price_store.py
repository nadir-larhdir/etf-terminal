from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine

from db.schema import create_tables
from stores.market.price_store import PriceStore


def test_price_store_round_trip_in_memory_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    create_tables(engine)
    store = PriceStore(engine)

    rows = pd.DataFrame(
        [
            {
                "ticker": "IEF",
                "date": "2024-01-02",
                "open": 95.0,
                "high": 96.0,
                "low": 94.5,
                "close": 95.5,
                "adj_close": 95.5,
                "volume": 1_000_000,
                "source": "test",
                "updated_at": "2024-01-02T00:00:00",
            },
            {
                "ticker": "IEF",
                "date": "2024-01-03",
                "open": 95.5,
                "high": 96.2,
                "low": 95.0,
                "close": 96.0,
                "adj_close": 96.0,
                "volume": 1_100_000,
                "source": "test",
                "updated_at": "2024-01-03T00:00:00",
            },
        ]
    )

    store.upsert_prices(rows)

    latest = store.get_latest_stored_dates(["IEF"])
    history = store.get_ticker_price_history("IEF")

    assert latest["IEF"] == "2024-01-03"
    assert len(history) == 2
    assert float(history["close"].iloc[-1]) == 96.0
