"""Structural interfaces the domain layer depends on, so services type-check against a
contract rather than a duck-typed object.

These are `Protocol`s, not base classes: the concrete stores already satisfy them and
need no changes, while tests can pass any object with the same shape.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias

import pandas as pd

DateLike: TypeAlias = "str | pd.Timestamp | None"


class MacroSeriesReader(Protocol):
    """Read access to raw macro time series."""

    def get_series_matrix(
        self,
        series_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame: ...

    def get_latest_stored_dates(self, series_ids: list[str] | None = None) -> dict[str, str]: ...


class MacroFeatureReader(Protocol):
    """Read access to derived macro features."""

    def get_feature_matrix(
        self,
        feature_names: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame: ...

    def get_recent_feature_matrix(
        self, feature_names: list[str], sessions: int = 2
    ) -> pd.DataFrame: ...

    def get_latest_feature_values(self, feature_names: list[str]) -> pd.DataFrame: ...

    def get_latest_feature_date(self) -> str | None: ...


class PriceHistoryReader(Protocol):
    """Read access to ETF end-of-day price history."""

    # Which database this reads from; cache entries are namespaced by it.
    engine: Any

    def get_ticker_price_history(
        self, ticker: str, start_date: DateLike = None, end_date: DateLike = None
    ) -> pd.DataFrame: ...

    def get_multi_ticker_price_history(
        self, tickers: list[str], start_date: DateLike = None, end_date: DateLike = None
    ) -> dict[str, pd.DataFrame]: ...

    def get_recent_price_history(
        self, tickers: list[str], sessions: int = 30
    ) -> dict[str, pd.DataFrame]: ...

    def get_latest_stored_dates(self, tickers: list[str] | None = None) -> dict[str, str]: ...


class MetadataReader(Protocol):
    """Read access to ETF issuer and provider metadata."""

    def get_ticker_metadata(self, ticker: str) -> dict[str, Any] | None: ...


class AnalyticsSnapshotStorage(Protocol):
    """Read and write access to precomputed ETF analytics snapshots."""

    def get_latest_snapshot(self, symbol: str) -> Any: ...

    def upsert_snapshot(self, snapshot: Any, *, as_of_date: str) -> None: ...


class MacroSeriesStore(MacroSeriesReader, Protocol):
    """Read and write access to raw macro time series."""

    def upsert_series(self, frame: pd.DataFrame) -> None: ...

    def replace_series(self, series_id: str, frame: pd.DataFrame) -> None: ...


class MacroFeatureStorage(MacroFeatureReader, Protocol):
    """Read and write access to derived macro features."""

    def upsert_features(self, df: pd.DataFrame) -> None: ...

    def delete_features(
        self, *, start_date: str | None = None, end_date: str | None = None
    ) -> None: ...


class PriceHistoryStorage(PriceHistoryReader, Protocol):
    """Read and write access to ETF price history."""

    def get_existing_tickers(self, tickers: list[str] | None = None) -> set[str]: ...

    def upsert_prices(self, df: pd.DataFrame) -> None: ...

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame) -> None: ...

    def delete_ticker(self, ticker: str) -> None: ...


class MetadataStorage(MetadataReader, Protocol):
    """Read and write access to ETF metadata."""

    def upsert_metadata(self, rows: list[dict[str, Any]]) -> None: ...

    def delete_ticker(self, ticker: str) -> None: ...


class ETFUniverseWriter(Protocol):
    """Write access to the active ETF universe."""

    def upsert_etfs(self, rows: list[dict[str, Any]], update_existing: bool = True) -> None: ...

    def delete_ticker(self, ticker: str) -> None: ...


class PriceHistorySyncer(Protocol):
    """Fetches and persists price history for a set of tickers."""

    def sync_price_history(
        self, tickers: list[str], period: str = "1y", replace_existing: bool = True
    ) -> None: ...


class MacroSeriesClient(Protocol):
    """Vendor client supplying macro observations and series metadata."""

    def get_series(
        self, series_id: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame: ...

    def get_series_metadata(self, series_id: str) -> dict[str, str]: ...
