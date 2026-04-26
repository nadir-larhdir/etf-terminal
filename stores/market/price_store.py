"""Read/write ETF daily price history rows."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from db.sql import pandas_to_sql_kwargs, qualified_table
from stores.query_utils import index_history_frame, latest_dates_map, sql_in_clause_params


class PriceStore:
    """Persist and retrieve OHLCV price history for ETF tickers."""

    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert_prices(self, df: pd.DataFrame) -> None:
        """Insert or update price rows, overwriting existing (ticker, date) pairs."""
        if df.empty:
            return
        statement = f"""
        INSERT INTO {qualified_table(self.engine, 'price_history')} (
            ticker, date, open, high, low, close, adj_close, volume, source, updated_at
        ) VALUES (
            :ticker, :date, :open, :high, :low, :close, :adj_close, :volume, :source, :updated_at
        )
        ON CONFLICT(ticker, date) DO UPDATE SET
            open = excluded.open, high = excluded.high, low = excluded.low,
            close = excluded.close, adj_close = excluded.adj_close,
            volume = excluded.volume, source = excluded.source, updated_at = excluded.updated_at
        """
        with self.engine.begin() as conn:
            conn.execute(text(statement), df.to_dict(orient="records"))

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame) -> None:
        """Delete all existing rows for ticker and insert the provided frame."""
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'price_history')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
            df.to_sql("price_history", conn, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine))

    def delete_ticker(self, ticker: str) -> None:
        """Remove all price rows for the given ticker."""
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'price_history')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_existing_tickers(self, tickers: list[str] | None = None) -> set[str]:
        """Return the set of tickers that have at least one price row stored."""
        normalized = tuple(sorted(tickers)) if tickers else None
        return self._existing_tickers(normalized)

    def get_latest_stored_dates(self, tickers: list[str] | None = None) -> dict[str, str]:
        """Return a mapping of ticker → latest stored date string."""
        normalized = tuple(sorted(tickers)) if tickers else None
        return self._latest_stored_dates(normalized)

    def get_ticker_price_history(self, ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
        """Return a date-indexed price history frame for a single ticker."""
        return self._ticker_price_history(ticker, start_date, end_date).copy()

    def get_multi_ticker_price_history(
        self, tickers: list[str], start_date=None, end_date=None
    ) -> dict[str, pd.DataFrame]:
        """Return a dict of ticker → date-indexed price history for multiple tickers."""
        normalized = tuple(sorted(dict.fromkeys(tickers)))
        frame = self._multi_ticker_history(normalized, start_date, end_date).copy()
        if frame.empty:
            return {}
        return {
            str(ticker): index_history_frame(ticker_frame.drop(columns=["ticker"]))
            for ticker, ticker_frame in frame.groupby("ticker", sort=False)
        }

    # ------------------------------------------------------------------
    # Private query helpers
    # ------------------------------------------------------------------

    def _existing_tickers(self, tickers: tuple[str, ...] | None) -> set[str]:
        query = f"SELECT DISTINCT ticker FROM {qualified_table(self.engine, 'price_history')}"
        params: dict = {}
        if tickers:
            placeholders, params = sql_in_clause_params("ticker", tickers)
            query += f" WHERE ticker IN ({placeholders})"
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        return set(df["ticker"].tolist()) if not df.empty else set()

    def _latest_stored_dates(self, tickers: tuple[str, ...] | None) -> dict[str, str]:
        query = f"SELECT ticker, MAX(date) AS latest_date FROM {qualified_table(self.engine, 'price_history')}"
        params: dict = {}
        if tickers:
            placeholders, params = sql_in_clause_params("ticker", tickers)
            query += f" WHERE ticker IN ({placeholders})"
        query += " GROUP BY ticker"
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        return latest_dates_map(df, key_column="ticker")

    def _ticker_price_history(self, ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
        query = f"""
        SELECT date, open, high, low, close, adj_close, volume
        FROM {qualified_table(self.engine, 'price_history')}
        WHERE ticker = :ticker
        """
        params: dict = {"ticker": ticker}
        if start_date is not None:
            query += " AND date >= :start_date"
            params["start_date"] = str(start_date)
        if end_date is not None:
            query += " AND date <= :end_date"
            params["end_date"] = str(end_date)
        query += " ORDER BY date"
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        return index_history_frame(df)

    def _multi_ticker_history(
        self, tickers: tuple[str, ...], start_date=None, end_date=None
    ) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"])
        placeholders, params = sql_in_clause_params("ticker", tickers)
        query = f"""
        SELECT ticker, date, open, high, low, close, adj_close, volume
        FROM {qualified_table(self.engine, 'price_history')}
        WHERE ticker IN ({placeholders})
        """
        if start_date is not None:
            query += " AND date >= :start_date"
            params["start_date"] = str(start_date)
        if end_date is not None:
            query += " AND date <= :end_date"
            params["end_date"] = str(end_date)
        query += " ORDER BY ticker, date"
        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params)
