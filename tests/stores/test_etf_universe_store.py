from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from stores.market.etf_universe_store import ETFUniverseStore


def _row(ticker: str, asset_class: str = "IG Credit", active: int = 1) -> dict[str, object]:
    return {
        "ticker": ticker,
        "name": f"{ticker} Bond ETF",
        "asset_class": asset_class,
        "active": active,
    }


@pytest.fixture
def store(engine: Engine) -> ETFUniverseStore:
    return ETFUniverseStore(engine)


def test_upserted_etfs_appear_in_the_active_list(store: ETFUniverseStore) -> None:
    store.upsert_etfs([_row("LQD"), _row("HYG", "HY Credit")])

    active = store.list_active_etfs()

    assert set(active["ticker"]) == {"LQD", "HYG"}


def test_the_active_list_is_ordered_by_ticker(store: ETFUniverseStore) -> None:
    store.upsert_etfs([_row("TLT"), _row("AGG"), _row("LQD")])

    assert list(store.list_active_etfs()["ticker"]) == ["AGG", "LQD", "TLT"]


def test_inactive_etfs_are_excluded_from_the_active_list(store: ETFUniverseStore) -> None:
    store.upsert_etfs([_row("LQD"), _row("OLD", active=0)])

    assert set(store.list_active_etfs()["ticker"]) == {"LQD"}


def test_upserting_an_existing_ticker_updates_its_asset_class(store: ETFUniverseStore) -> None:
    store.upsert_etfs([_row("LQD", "IG Credit")])
    store.upsert_etfs([_row("LQD", "Core Bond")])

    active = store.list_active_etfs()

    assert len(active) == 1
    assert active.iloc[0]["asset_class"] == "Core Bond"


def test_upserting_without_update_existing_keeps_the_original_row(store: ETFUniverseStore) -> None:
    store.upsert_etfs([_row("LQD", "IG Credit")])
    store.upsert_etfs([_row("LQD", "Core Bond")], update_existing=False)

    assert store.list_active_etfs().iloc[0]["asset_class"] == "IG Credit"


def test_upserting_no_rows_is_a_no_op(store: ETFUniverseStore) -> None:
    store.upsert_etfs([])

    assert store.get_existing_tickers() == set()


def test_replacing_the_universe_discards_everything_that_came_before(
    store: ETFUniverseStore,
) -> None:
    store.upsert_etfs([_row("LQD"), _row("HYG")])

    store.replace_etf_universe([_row("AGG")])

    assert store.get_existing_tickers() == {"AGG"}


def test_deleting_a_ticker_removes_only_that_ticker(store: ETFUniverseStore) -> None:
    store.upsert_etfs([_row("LQD"), _row("HYG")])

    store.delete_ticker("LQD")

    assert store.get_existing_tickers() == {"HYG"}
