import pandas as pd
import streamlit as st
from sqlalchemy import text

from db.sql import cache_scope, pandas_to_sql_kwargs, qualified_table
from stores.query_utils import index_history_frame, latest_dates_map


@st.cache_data(ttl=300, show_spinner=False)
def _cached_existing_tickers(_cache_key: str, _engine, tickers: tuple[str, ...] | None) -> set[str]:
    query = f"SELECT DISTINCT ticker FROM {qualified_table(_engine, 'price_history')}"
    params = {}

    if tickers:
        placeholders = ", ".join(f":ticker_{idx}" for idx in range(len(tickers)))
        query += f" WHERE ticker IN ({placeholders})"
        params = {f"ticker_{idx}": ticker for idx, ticker in enumerate(tickers)}

    with _engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    return set(df["ticker"].tolist()) if not df.empty else set()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_latest_stored_dates(_cache_key: str, _engine, tickers: tuple[str, ...] | None) -> dict[str, str]:
    query = f"""
    SELECT ticker, MAX(date) AS latest_date
    FROM {qualified_table(_engine, 'price_history')}
    """
    params = {}

    if tickers:
        placeholders = ", ".join(f":ticker_{idx}" for idx in range(len(tickers)))
        query += f" WHERE ticker IN ({placeholders})"
        params = {f"ticker_{idx}": ticker for idx, ticker in enumerate(tickers)}

    query += " GROUP BY ticker"

    with _engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    return latest_dates_map(df, key_column="ticker")


@st.cache_data(ttl=300, show_spinner=False)
def _cached_ticker_price_history(_cache_key: str, _engine, ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
    query = f"""
    SELECT date, open, high, low, close, adj_close, volume
    FROM {qualified_table(_engine, 'price_history')}
    WHERE ticker = :ticker
    """
    params = {"ticker": ticker}

    if start_date is not None:
        query += " AND date >= :start_date"
        params["start_date"] = str(start_date)

    if end_date is not None:
        query += " AND date <= :end_date"
        params["end_date"] = str(end_date)

    query += " ORDER BY date"

    with _engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    return index_history_frame(df)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_multi_ticker_history(_cache_key: str, _engine, tickers: tuple[str, ...], start_date=None, end_date=None) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame(columns=["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"])

    placeholders = ", ".join(f":ticker_{idx}" for idx in range(len(tickers)))
    query = f"""
    SELECT ticker, date, open, high, low, close, adj_close, volume
    FROM {qualified_table(_engine, 'price_history')}
    WHERE ticker IN ({placeholders})
    """
    params = {f"ticker_{idx}": ticker for idx, ticker in enumerate(tickers)}

    if start_date is not None:
        query += " AND date >= :start_date"
        params["start_date"] = str(start_date)

    if end_date is not None:
        query += " AND date <= :end_date"
        params["end_date"] = str(end_date)

    query += " ORDER BY ticker, date"

    with _engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


class PriceStore:
    """Read and write ETF daily price history rows."""

    def __init__(self, engine):
        self.engine = engine

    def _clear_caches(self) -> None:
        _cached_existing_tickers.clear()
        _cached_latest_stored_dates.clear()
        _cached_ticker_price_history.clear()
        _cached_multi_ticker_history.clear()

    def upsert_prices(self, df: pd.DataFrame):
        if df.empty:
            return

        records = df.to_dict(orient="records")
        statement = """
        INSERT INTO {price_table} (
            ticker,
            date,
            open,
            high,
            low,
            close,
            adj_close,
            volume,
            source,
            updated_at
        ) VALUES (
            :ticker,
            :date,
            :open,
            :high,
            :low,
            :close,
            :adj_close,
            :volume,
            :source,
            :updated_at
        )
        ON CONFLICT(ticker, date) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            adj_close = excluded.adj_close,
            volume = excluded.volume,
            source = excluded.source,
            updated_at = excluded.updated_at
        """.format(price_table=qualified_table(self.engine, "price_history"))
        with self.engine.begin() as conn:
            conn.execute(text(statement), records)
        self._clear_caches()

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'price_history')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
            df.to_sql("price_history", conn, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine))
        self._clear_caches()

    def get_existing_tickers(self, tickers: list[str] | None = None) -> set[str]:
        normalized = tuple(sorted(tickers)) if tickers else None
        return _cached_existing_tickers(cache_scope(self.engine), self.engine, normalized)

    def get_latest_stored_dates(self, tickers: list[str] | None = None) -> dict[str, str]:
        normalized = tuple(sorted(tickers)) if tickers else None
        return _cached_latest_stored_dates(cache_scope(self.engine), self.engine, normalized)

    def get_ticker_price_history(self, ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
        return _cached_ticker_price_history(cache_scope(self.engine), self.engine, ticker, start_date, end_date).copy()

    def get_multi_ticker_price_history(self, tickers: list[str], start_date=None, end_date=None) -> dict[str, pd.DataFrame]:
        normalized = tuple(sorted(dict.fromkeys(tickers)))
        frame = _cached_multi_ticker_history(cache_scope(self.engine), self.engine, normalized, start_date, end_date).copy()
        if frame.empty:
            return {}

        grouped: dict[str, pd.DataFrame] = {}
        for ticker, ticker_frame in frame.groupby("ticker", sort=False):
            grouped[str(ticker)] = index_history_frame(ticker_frame.drop(columns=["ticker"]))
        return grouped

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'price_history')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
        self._clear_caches()
