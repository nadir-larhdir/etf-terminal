from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from stores.market.metadata_store import MetadataStore


def _row(ticker: str, **overrides: object) -> dict[str, object]:
    row = {
        "ticker": ticker,
        "long_name": f"{ticker} Bond ETF",
        "issuer": "iShares",
        "duration": 6.4,
        "yield_to_maturity": 4.8,
        "oas": 120.0,
        "category": "IG Credit",
        "source": "test",
    }
    row.update(overrides)
    return row


@pytest.fixture
def store(engine: Engine) -> MetadataStore:
    return MetadataStore(engine)


def test_metadata_round_trips_for_a_single_ticker(store: MetadataStore) -> None:
    store.upsert_metadata([_row("LQD")])

    metadata = store.get_ticker_metadata("LQD")

    assert metadata is not None
    assert metadata["issuer"] == "iShares"
    assert float(metadata["duration"]) == 6.4


def test_upserting_the_same_ticker_updates_in_place(store: MetadataStore) -> None:
    store.upsert_metadata([_row("LQD", duration=6.4)])
    store.upsert_metadata([_row("LQD", duration=7.1)])

    metadata = store.get_ticker_metadata("LQD")

    assert metadata is not None and float(metadata["duration"]) == 7.1
    assert store.get_existing_tickers() == {"LQD"}


def test_an_unknown_ticker_has_no_metadata(store: MetadataStore) -> None:
    assert store.get_ticker_metadata("NOPE") is None


def test_upserting_no_rows_is_a_no_op(store: MetadataStore) -> None:
    store.upsert_metadata([])

    assert store.get_existing_tickers() == set()


def test_rows_missing_optional_columns_are_still_accepted(store: MetadataStore) -> None:
    store.upsert_metadata([{"ticker": "TLT", "source": "test"}])

    metadata = store.get_ticker_metadata("TLT")

    assert metadata is not None and metadata["ticker"] == "TLT"


def test_an_upsert_stamps_updated_at_when_the_caller_omits_it(store: MetadataStore) -> None:
    store.upsert_metadata([{"ticker": "TLT", "source": "test"}])

    metadata = store.get_ticker_metadata("TLT")

    assert metadata is not None and metadata["updated_at"]


def test_existing_tickers_lists_every_stored_row(store: MetadataStore) -> None:
    store.upsert_metadata([_row("LQD"), _row("HYG")])

    assert store.get_existing_tickers() == {"LQD", "HYG"}


def test_deleting_a_ticker_leaves_the_others_in_place(store: MetadataStore) -> None:
    store.upsert_metadata([_row("LQD"), _row("HYG")])

    store.delete_ticker("LQD")

    assert store.get_existing_tickers() == {"HYG"}
    assert store.get_ticker_metadata("LQD") is None
