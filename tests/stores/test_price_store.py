from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from stores.market.price_store import PriceStore


def _rows(ticker: str, dates: list[str], closes: list[float] | None = None) -> pd.DataFrame:
    closes = closes or [100.0 + i for i in range(len(dates))]
    return pd.DataFrame(
        [
            {
                "ticker": ticker,
                "date": date,
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "adj_close": close,
                "volume": 1_000_000 + index,
                "source": "test",
                "updated_at": f"{date}T00:00:00",
            }
            for index, (date, close) in enumerate(zip(dates, closes, strict=True))
        ]
    )


@pytest.fixture
def store(engine: Engine) -> PriceStore:
    return PriceStore(engine)


def test_upserted_rows_round_trip_as_a_date_indexed_history(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02", "2024-01-03"]))

    history = store.get_ticker_price_history("IEF")

    assert len(history) == 2
    assert isinstance(history.index, pd.DatetimeIndex)
    assert float(history["close"].iloc[-1]) == 101.0


def test_upserting_the_same_date_updates_rather_than_duplicates(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02"], [100.0]))
    store.upsert_prices(_rows("IEF", ["2024-01-02"], [123.0]))

    history = store.get_ticker_price_history("IEF")

    assert len(history) == 1
    assert float(history["close"].iloc[0]) == 123.0


def test_upserting_an_empty_frame_is_a_no_op(store: PriceStore) -> None:
    store.upsert_prices(pd.DataFrame())

    assert store.get_existing_tickers() == set()


def test_history_is_returned_in_date_order_regardless_of_insert_order(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-05", "2024-01-02", "2024-01-03"]))

    history = store.get_ticker_price_history("IEF")

    assert list(history.index) == sorted(history.index)


def test_history_can_be_bounded_at_both_ends(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02", "2024-01-03", "2024-01-04"]))

    history = store.get_ticker_price_history("IEF", "2024-01-03", "2024-01-03")

    assert len(history) == 1


def test_an_unknown_ticker_returns_an_empty_history(store: PriceStore) -> None:
    assert store.get_ticker_price_history("NOPE").empty


def test_latest_stored_dates_report_the_newest_row_per_ticker(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02", "2024-01-05"]))
    store.upsert_prices(_rows("HYG", ["2024-01-03"]))

    assert store.get_latest_stored_dates() == {"IEF": "2024-01-05", "HYG": "2024-01-03"}


def test_latest_stored_dates_can_be_narrowed_to_requested_tickers(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02"]))
    store.upsert_prices(_rows("HYG", ["2024-01-03"]))

    assert set(store.get_latest_stored_dates(["IEF"])) == {"IEF"}


def test_multi_ticker_history_returns_one_frame_per_requested_ticker(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02", "2024-01-03"]))
    store.upsert_prices(_rows("HYG", ["2024-01-02"]))

    histories = store.get_multi_ticker_price_history(["IEF", "HYG"])

    assert len(histories["IEF"]) == 2
    assert len(histories["HYG"]) == 1


def test_multi_ticker_history_omits_tickers_with_no_rows(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02"]))

    histories = store.get_multi_ticker_price_history(["IEF", "NOPE"])

    assert histories.get("NOPE") is None or histories["NOPE"].empty


def test_replacing_a_ticker_drops_the_rows_it_had_before(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02", "2024-01-03"]))

    store.replace_ticker_prices("IEF", _rows("IEF", ["2024-02-01"], [200.0]))

    history = store.get_ticker_price_history("IEF")
    assert len(history) == 1
    assert float(history["close"].iloc[0]) == 200.0


def test_replacing_leaves_other_tickers_untouched(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02"]))
    store.upsert_prices(_rows("HYG", ["2024-01-02"]))

    store.replace_ticker_prices("IEF", _rows("IEF", ["2024-02-01"]))

    assert len(store.get_ticker_price_history("HYG")) == 1


def test_deleting_a_ticker_removes_it_from_the_store(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02"]))
    store.upsert_prices(_rows("HYG", ["2024-01-02"]))

    store.delete_ticker("IEF")

    assert store.get_existing_tickers() == {"HYG"}


def test_existing_tickers_can_be_intersected_with_a_requested_list(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-02"]))
    store.upsert_prices(_rows("HYG", ["2024-01-02"]))

    assert store.get_existing_tickers(["IEF", "NOPE"]) == {"IEF"}


# ── windowed reads ──────────────────────────────────────────────────────────


def test_recent_history_returns_only_the_requested_tail(store: PriceStore) -> None:
    """The window is applied in SQL: the homepage needs a tail, not whole histories."""
    dates = [f"2024-01-{day:02d}" for day in range(1, 21)]
    store.upsert_prices(_rows("IEF", dates))

    recent = store.get_recent_price_history(["IEF"], sessions=5)

    assert len(recent["IEF"]) == 5


def test_recent_history_returns_the_newest_rows_oldest_first(store: PriceStore) -> None:
    dates = [f"2024-01-{day:02d}" for day in range(1, 11)]
    store.upsert_prices(_rows("IEF", dates))

    frame = store.get_recent_price_history(["IEF"], sessions=3)["IEF"]

    assert [str(d.date()) for d in frame.index] == ["2024-01-08", "2024-01-09", "2024-01-10"]


def test_recent_history_matches_the_tail_of_the_full_history(store: PriceStore) -> None:
    dates = [f"2024-01-{day:02d}" for day in range(1, 16)]
    store.upsert_prices(_rows("IEF", dates))

    windowed = store.get_recent_price_history(["IEF"], sessions=4)["IEF"]
    full = store.get_ticker_price_history("IEF").tail(4)

    assert windowed["close"].tolist() == full["close"].tolist()


def test_recent_history_windows_each_ticker_independently(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-01", "2024-01-02", "2024-01-03"]))
    store.upsert_prices(_rows("HYG", ["2024-01-02"]))

    recent = store.get_recent_price_history(["IEF", "HYG"], sessions=2)

    assert len(recent["IEF"]) == 2
    assert len(recent["HYG"]) == 1


def test_recent_history_of_an_unknown_ticker_is_omitted(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-01"]))

    assert set(store.get_recent_price_history(["IEF", "NOPE"], sessions=5)) == {"IEF"}


@pytest.mark.parametrize(("tickers", "sessions"), [([], 5), (["IEF"], 0), ([], 0)])
def test_recent_history_of_a_degenerate_request_is_empty(
    store: PriceStore, tickers: list[str], sessions: int
) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-01"]))

    assert store.get_recent_price_history(tickers, sessions=sessions) == {}


def test_recent_history_carries_the_ohlcv_columns(store: PriceStore) -> None:
    store.upsert_prices(_rows("IEF", ["2024-01-01", "2024-01-02"]))

    frame = store.get_recent_price_history(["IEF"], sessions=2)["IEF"]

    assert {"open", "high", "low", "close", "adj_close", "volume"} <= set(frame.columns)
    assert "ticker" not in frame.columns
