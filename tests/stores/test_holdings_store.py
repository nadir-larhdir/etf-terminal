from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from stores.market.holdings_store import HoldingsStore


def _holdings(names: list[str], weights: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "name": names,
            "weight": weights,
            "cusip": [f"CUSIP{i}" for i in range(len(names))],
            "coupon": [4.5] * len(names),
            "maturity_dt": ["2030-06-30"] * len(names),
        }
    )


@pytest.fixture
def store(engine: Engine) -> HoldingsStore:
    return HoldingsStore(engine)


def test_a_snapshot_round_trips_for_a_ticker(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", _holdings(["A", "B"], [2.0, 1.0]), as_of_date="2026-08-21")

    holdings = store.get_latest_holdings("LQD")

    assert len(holdings) == 2
    assert set(holdings["name"]) == {"A", "B"}


def test_holdings_are_stored_ranked_by_weight(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", _holdings(["small", "big"], [1.0, 9.0]), as_of_date="2026-08-21")

    holdings = store.get_latest_holdings("LQD")

    assert list(holdings["name"]) == ["big", "small"]
    assert list(holdings["position"]) == [1, 2]


def test_the_ticker_is_normalised_to_upper_case_on_both_sides(store: HoldingsStore) -> None:
    store.replace_holdings("lqd", _holdings(["A"], [1.0]), as_of_date="2026-08-21")

    assert len(store.get_latest_holdings("LQD")) == 1
    assert len(store.get_latest_holdings("lqd")) == 1


def test_replacing_the_same_date_does_not_duplicate_rows(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", _holdings(["A", "B"], [2.0, 1.0]), as_of_date="2026-08-21")
    store.replace_holdings("LQD", _holdings(["C"], [3.0]), as_of_date="2026-08-21")

    holdings = store.get_latest_holdings("LQD")

    assert list(holdings["name"]) == ["C"]


def test_only_the_newest_snapshot_is_returned(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", _holdings(["old"], [1.0]), as_of_date="2026-08-20")
    store.replace_holdings("LQD", _holdings(["new"], [1.0]), as_of_date="2026-08-21")

    assert list(store.get_latest_holdings("LQD")["name"]) == ["new"]


def test_a_limit_truncates_to_the_largest_positions(store: HoldingsStore) -> None:
    store.replace_holdings(
        "LQD", _holdings(["a", "b", "c"], [1.0, 3.0, 2.0]), as_of_date="2026-08-21"
    )

    assert list(store.get_latest_holdings("LQD", limit=2)["name"]) == ["b", "c"]


def test_an_empty_frame_is_not_persisted(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", pd.DataFrame(), as_of_date="2026-08-21")

    assert store.get_latest_as_of_date("LQD") is None


def test_an_unknown_ticker_has_no_snapshot(store: HoldingsStore) -> None:
    assert store.get_latest_holdings("NOPE").empty
    assert store.get_latest_as_of_date("NOPE") is None


def test_the_latest_as_of_date_reports_the_newest_snapshot(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", _holdings(["a"], [1.0]), as_of_date="2026-08-20")
    store.replace_holdings("LQD", _holdings(["b"], [1.0]), as_of_date="2026-08-21")

    assert store.get_latest_as_of_date("LQD") == "2026-08-21"


def test_the_snapshot_date_defaults_to_today_when_omitted(store: HoldingsStore) -> None:
    from datetime import date

    store.replace_holdings("LQD", _holdings(["a"], [1.0]))

    assert store.get_latest_as_of_date("LQD") == date.today().isoformat()


def test_snapshots_for_different_tickers_stay_separate(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", _holdings(["a"], [1.0]), as_of_date="2026-08-21")
    store.replace_holdings("HYG", _holdings(["b", "c"], [1.0, 2.0]), as_of_date="2026-08-21")

    assert len(store.get_latest_holdings("LQD")) == 1
    assert len(store.get_latest_holdings("HYG")) == 2


def test_holdings_with_no_weight_column_are_still_stored(store: HoldingsStore) -> None:
    store.replace_holdings("LQD", pd.DataFrame({"name": ["a", "b"]}), as_of_date="2026-08-21")

    assert len(store.get_latest_holdings("LQD")) == 2
