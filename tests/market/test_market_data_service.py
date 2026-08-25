from __future__ import annotations

import pandas as pd
import pytest

from services.market.market_data_service import MarketDataService
from tests.fakes import FakePriceStore


class _StubFMP:
    """Returns canned price history and records the windows it was asked for."""

    def __init__(self, rows: dict[str, list[str]] | None = None) -> None:
        self.rows = rows or {}
        self.calls: list[tuple[str, str | None, str | None, str | None]] = []

    def get_historical_price_eod_full(
        self,
        symbol: str,
        *,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        self.calls.append((symbol, period, start, end))
        dates = self.rows.get(symbol, [])
        if not dates:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "date": date,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "adj_close": 100.5,
                    "volume": 1_000_000,
                    "ticker": symbol,
                }
                for date in dates
            ]
        )


def _service(rows: dict[str, list[str]] | None = None) -> tuple[MarketDataService, FakePriceStore]:
    store = FakePriceStore()
    service = MarketDataService(store)
    service.fmp_client = _StubFMP(rows)  # type: ignore[assignment]
    return service, store


# ── ticker normalisation ────────────────────────────────────────────────────


def test_tickers_are_uppercased_deduplicated_and_kept_in_order() -> None:
    service, _ = _service()

    assert service._normalise_tickers([" ief", "HYG", "ief", "", " tlt "]) == ["IEF", "HYG", "TLT"]


def test_an_empty_ticker_list_normalises_to_nothing() -> None:
    service, _ = _service()

    assert service._normalise_tickers(["", "   "]) == []


# ── full sync ───────────────────────────────────────────────────────────────


def test_a_full_sync_replaces_each_ticker_s_history() -> None:
    service, store = _service({"IEF": ["2026-08-20", "2026-08-21"]})

    service.sync_price_history(["ief"])

    assert [ticker for ticker, _ in store.replacements] == ["IEF"]
    assert not store.upserts


def test_a_gap_fill_upserts_instead_of_replacing() -> None:
    service, store = _service({"IEF": ["2026-08-21"]})

    service.sync_price_gaps(["IEF"])

    assert store.upserts and not store.replacements


def test_a_ticker_the_vendor_has_no_data_for_is_not_persisted() -> None:
    service, store = _service({})

    service.sync_price_history(["IEF"])

    assert not store.replacements and not store.upserts


def test_persisted_rows_are_stamped_with_their_source() -> None:
    service, store = _service({"IEF": ["2026-08-21"]})

    service.sync_price_history(["IEF"])

    _, frame = store.replacements[0]
    assert set(frame["source"]) == {"fmp"}
    assert frame["updated_at"].notna().all()


def test_each_ticker_is_persisted_with_only_its_own_rows() -> None:
    service, store = _service({"IEF": ["2026-08-21"], "HYG": ["2026-08-21", "2026-08-20"]})

    service.sync_price_history(["IEF", "HYG"])

    persisted = {ticker: len(frame) for ticker, frame in store.replacements}
    assert persisted == {"IEF": 1, "HYG": 2}


# ── missing-ticker initialisation ───────────────────────────────────────────


def test_only_tickers_with_no_stored_rows_are_initialised() -> None:
    service, store = _service({"HYG": ["2026-08-21"]})
    store.histories["IEF"] = pd.DataFrame()

    missing = service.sync_missing_ticker_history(["IEF", "HYG"])

    assert missing == ["HYG"]


def test_nothing_is_fetched_when_every_ticker_already_exists() -> None:
    service, store = _service({"IEF": ["2026-08-21"]})
    store.histories["IEF"] = pd.DataFrame()

    assert service.sync_missing_ticker_history(["IEF"]) == []
    assert not store.upserts


# ── incremental sync ────────────────────────────────────────────────────────


def test_a_ticker_with_no_history_is_reported_as_initialised() -> None:
    service, _ = _service({"IEF": ["2026-08-21"]})

    statuses = service.sync_incremental_updates(["IEF"], period_for_new="2y")

    assert statuses == {"IEF": "initialized_2y"}


def test_an_existing_ticker_is_refetched_from_its_last_date_less_the_overlap() -> None:
    service, store = _service({"IEF": ["2026-08-21"]})
    store.latest_dates = {"IEF": "2026-08-21"}

    statuses = service.sync_incremental_updates(["IEF"], overlap_days=5)

    assert statuses == {"IEF": "updated_from_2026-08-16"}


def test_an_existing_ticker_with_no_new_bars_is_reported_as_such() -> None:
    service, store = _service({})
    store.latest_dates = {"IEF": "2026-08-21"}

    assert service.sync_incremental_updates(["IEF"]) == {"IEF": "no_new_rows"}


def test_new_and_existing_tickers_are_both_reported_in_one_pass() -> None:
    service, store = _service({"IEF": ["2026-08-21"], "HYG": ["2026-08-21"]})
    store.latest_dates = {"IEF": "2026-08-21"}

    statuses = service.sync_incremental_updates(["IEF", "HYG"])

    assert set(statuses) == {"IEF", "HYG"}
    assert statuses["HYG"].startswith("initialized")
    assert statuses["IEF"].startswith("updated_from")


def test_an_incremental_sync_never_deletes_existing_rows() -> None:
    service, store = _service({"IEF": ["2026-08-21"]})
    store.latest_dates = {"IEF": "2026-08-21"}

    service.sync_incremental_updates(["IEF"])

    assert not store.replacements


def test_the_incremental_fetch_window_starts_at_the_earliest_ticker() -> None:
    service, store = _service({"IEF": ["2026-08-21"], "HYG": ["2026-08-21"]})
    store.latest_dates = {"IEF": "2026-08-21", "HYG": "2026-06-01"}

    service.sync_incremental_updates(["IEF", "HYG"], overlap_days=0)

    starts = {call[2] for call in service.fmp_client.calls}  # type: ignore[attr-defined]
    assert starts == {"2026-06-01"}


def test_syncing_an_empty_ticker_list_does_nothing() -> None:
    service, store = _service()

    assert service.sync_incremental_updates([]) == {}
    assert not store.upserts and not store.replacements


@pytest.mark.parametrize("overlap", [0, 5, 30])
def test_the_overlap_window_shifts_the_refetch_start(overlap: int) -> None:
    service, store = _service({"IEF": ["2026-08-21"]})
    store.latest_dates = {"IEF": "2026-08-21"}

    statuses = service.sync_incremental_updates(["IEF"], overlap_days=overlap)

    expected = (pd.Timestamp("2026-08-21") - pd.Timedelta(days=overlap)).date().isoformat()
    assert statuses["IEF"] == f"updated_from_{expected}"
