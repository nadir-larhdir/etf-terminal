"""In-memory test doubles that fully satisfy the store and HTTP protocols.

Each fake implements its protocol completely, so type checking a test that passes one is
a real check that the production call sites would work. Shared here rather than redefined
per test module.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _slice_by_date(frame: pd.DataFrame, start_date: Any, end_date: Any) -> pd.DataFrame:
    """Restrict a date-indexed frame to an inclusive range."""
    if frame.empty:
        return frame
    if start_date is not None:
        frame = frame.loc[frame.index >= pd.Timestamp(start_date)]
    if end_date is not None:
        frame = frame.loc[frame.index <= pd.Timestamp(end_date)]
    return frame


class FakePriceStore:
    """Serves preloaded price history and records nothing else."""

    def __init__(self, histories: dict[str, pd.DataFrame] | None = None) -> None:
        self.histories = histories or {}
        self.engine: Any = None
        self.latest_dates: dict[str, str] = {}
        self.upserts: list[pd.DataFrame] = []
        self.replacements: list[tuple[str, pd.DataFrame]] = []
        self.deleted: list[str] = []

    def get_ticker_price_history(
        self, ticker: str, start_date: Any = None, end_date: Any = None
    ) -> pd.DataFrame:
        return _slice_by_date(
            self.histories.get(ticker, pd.DataFrame()).copy(), start_date, end_date
        )

    def get_multi_ticker_price_history(
        self, tickers: list[str], start_date: Any = None, end_date: Any = None
    ) -> dict[str, pd.DataFrame]:
        return {
            ticker: self.get_ticker_price_history(ticker, start_date, end_date)
            for ticker in tickers
        }

    def get_recent_price_history(
        self, tickers: list[str], sessions: int = 30
    ) -> dict[str, pd.DataFrame]:
        return {
            ticker: frame.tail(sessions).copy()
            for ticker in tickers
            if not (frame := self.histories.get(ticker, pd.DataFrame())).empty
        }

    def get_latest_stored_dates(self, tickers: list[str] | None = None) -> dict[str, str]:
        if tickers is None:
            return dict(self.latest_dates)
        return {t: self.latest_dates[t] for t in tickers if t in self.latest_dates}

    def get_existing_tickers(self, tickers: list[str] | None = None) -> set[str]:
        known = set(self.histories)
        return known if tickers is None else known & set(tickers)

    def upsert_prices(self, df: pd.DataFrame) -> None:
        self.upserts.append(df.copy())

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame) -> None:
        self.replacements.append((ticker, df.copy()))
        self.histories[ticker] = df.copy()

    def delete_ticker(self, ticker: str) -> None:
        self.deleted.append(ticker)
        self.histories.pop(ticker, None)


class FakeMacroStore:
    """Serves a preloaded wide series matrix and captures writes."""

    def __init__(
        self,
        matrix: pd.DataFrame | None = None,
        latest_dates: dict[str, str] | None = None,
    ) -> None:
        self.matrix = pd.DataFrame() if matrix is None else matrix
        self.latest_dates = latest_dates or {}
        self.upserts: list[pd.DataFrame] = []
        self.replacements: list[tuple[str, pd.DataFrame]] = []

    def get_series_matrix(
        self,
        series_ids: list[str] | None = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> pd.DataFrame:
        frame = _slice_by_date(self.matrix.copy(), start_date, end_date)
        return frame.loc[:, list(series_ids)] if series_ids else frame

    def get_latest_stored_dates(self, series_ids: list[str] | None = None) -> dict[str, str]:
        if series_ids is None:
            return dict(self.latest_dates)
        return {s: self.latest_dates[s] for s in series_ids if s in self.latest_dates}

    def upsert_series(self, frame: pd.DataFrame) -> None:
        self.upserts.append(frame.copy())

    def replace_series(self, series_id: str, frame: pd.DataFrame) -> None:
        self.replacements.append((series_id, frame.copy()))


class FakeMacroFeatureStore:
    """Serves a preloaded feature matrix and captures writes and deletes."""

    def __init__(self, matrix: pd.DataFrame | None = None, latest_date: str | None = None) -> None:
        self.matrix = pd.DataFrame() if matrix is None else matrix
        self.latest_date = latest_date
        self.upserts: list[pd.DataFrame] = []
        self.deleted_ranges: list[tuple[str | None, str | None]] = []

    def get_feature_matrix(
        self,
        feature_names: list[str] | None = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> pd.DataFrame:
        frame = _slice_by_date(self.matrix.copy(), start_date, end_date)
        if not feature_names:
            return frame
        present = [name for name in feature_names if name in frame.columns]
        return frame.loc[:, present]

    def get_recent_feature_matrix(
        self, feature_names: list[str], sessions: int = 2
    ) -> pd.DataFrame:
        return self.get_feature_matrix(feature_names).tail(sessions)

    def get_latest_feature_values(self, feature_names: list[str]) -> pd.DataFrame:
        if self.matrix.empty:
            return pd.DataFrame(columns=["feature_name", "date", "value"])
        last = self.matrix.iloc[-1]
        return pd.DataFrame(
            [
                {"feature_name": name, "date": self.matrix.index[-1], "value": last[name]}
                for name in feature_names
                if name in self.matrix.columns
            ]
        )

    def get_latest_feature_date(self) -> str | None:
        return self.latest_date

    def upsert_features(self, df: pd.DataFrame) -> None:
        self.upserts.append(df.copy())

    def delete_features(
        self, *, start_date: str | None = None, end_date: str | None = None
    ) -> None:
        self.deleted_ranges.append((start_date, end_date))

    @property
    def last_frame(self) -> pd.DataFrame:
        """The most recently upserted frame, for assertions."""
        return self.upserts[-1]


class FakeMetadataStore:
    """Serves preloaded per-ticker metadata."""

    def __init__(self, metadata: dict[str, dict[str, Any]] | None = None) -> None:
        self.metadata = metadata or {}
        self.rows: list[dict[str, Any]] = []
        self.deleted: list[str] = []

    def get_ticker_metadata(self, ticker: str) -> dict[str, Any] | None:
        return self.metadata.get(ticker)

    def get_existing_tickers(self) -> set[str]:
        return set(self.metadata)

    def upsert_metadata(self, rows: list[dict[str, Any]]) -> None:
        self.rows.extend(rows)
        for row in rows:
            self.metadata[str(row.get("ticker", ""))] = row

    def delete_ticker(self, ticker: str) -> None:
        self.deleted.append(ticker)
        self.metadata.pop(ticker, None)


class FakeSnapshotStore:
    """Holds analytics snapshots in memory, keyed by symbol."""

    def __init__(self, snapshots: dict[str, Any] | None = None) -> None:
        self.snapshots = snapshots or {}
        self.upserts: list[tuple[Any, str]] = []

    def get_latest_snapshot(self, symbol: str) -> Any:
        return self.snapshots.get(symbol)

    def upsert_snapshot(self, snapshot: Any, *, as_of_date: str) -> None:
        self.upserts.append((snapshot, as_of_date))
        self.snapshots[getattr(snapshot, "ticker", "")] = snapshot


class FakeResponse:
    """A requests-like response returning a fixed payload."""

    def __init__(self, payload: Any = None, *, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        if self.error is not None:
            raise self.error
        return self.payload


class FakeSession:
    """A requests-like session that records calls and replays queued responses."""

    def __init__(self, *responses: Any) -> None:
        flat = (
            responses[0] if len(responses) == 1 and isinstance(responses[0], tuple) else responses
        )
        self.responses = [
            r if isinstance(r, FakeResponse | Exception) else FakeResponse(r) for r in flat
        ]
        self.calls: list[tuple[str, dict[str, Any], int]] = []

    def get(self, url: str, *, params: dict[str, Any], timeout: int) -> FakeResponse:
        self.calls.append((url, params, timeout))
        nxt = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class FakeUniverseStore:
    """Captures ETF universe writes."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.deleted: list[str] = []

    def upsert_etfs(self, rows: list[dict[str, Any]], update_existing: bool = True) -> None:
        self.rows.extend(rows)

    def delete_ticker(self, ticker: str) -> None:
        self.deleted.append(ticker)


class FakePriceSyncer:
    """Records sync_price_history calls without touching the network."""

    def __init__(self) -> None:
        self.synced: list[tuple[list[str], str, bool]] = []

    def sync_price_history(
        self, tickers: list[str], period: str = "1y", replace_existing: bool = True
    ) -> None:
        self.synced.append((tickers, period, replace_existing))


class FakeMacroClient:
    """Returns one synthetic observation per series, plus echo metadata."""

    def get_series(
        self, series_id: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        return pd.DataFrame([{"series_id": series_id, "date": start or "2024-01-01", "value": 1.0}])

    def get_series_metadata(self, series_id: str) -> dict[str, str]:
        return {"title": series_id, "frequency": "Daily", "units": "Percent"}
