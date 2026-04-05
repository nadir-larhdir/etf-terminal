import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime

from db.sql import pandas_to_sql_kwargs, qualified_table


@st.cache_data(ttl=900, show_spinner=False)
def _cached_existing_metadata_tickers(_cache_key: str, _engine) -> set[str]:
    with _engine.connect() as conn:
        df = pd.read_sql(text(f"SELECT ticker FROM {qualified_table(_engine, 'security_metadata')}"), conn)
    return set(df["ticker"].tolist()) if not df.empty else set()


@st.cache_data(ttl=900, show_spinner=False)
def _cached_ticker_metadata(_cache_key: str, _engine, ticker: str):
    query = text(
        f"""
        SELECT *
        FROM {qualified_table(_engine, 'security_metadata')}
        WHERE ticker = :ticker
        LIMIT 1
        """
    )
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"ticker": ticker})
    return df.iloc[0].to_dict() if not df.empty else None


class MetadataStore:
    """Read and write descriptive ETF metadata rows."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_metadata(self, rows):
        if not rows:
            return

        df = pd.DataFrame(rows)
        if "updated_at" not in df.columns:
            df["updated_at"] = datetime.utcnow().isoformat()

        tickers = df["ticker"].dropna().astype(str).tolist()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'security_metadata')} WHERE ticker = :ticker"),
                [{"ticker": ticker} for ticker in tickers],
            )
            df.to_sql("security_metadata", conn, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine))
        _cached_existing_metadata_tickers.clear()
        _cached_ticker_metadata.clear()

    def get_existing_tickers(self) -> set[str]:
        return _cached_existing_metadata_tickers(str(self.engine.url), self.engine)

    def get_ticker_metadata(self, ticker: str):
        return _cached_ticker_metadata(str(self.engine.url), self.engine, ticker)

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'security_metadata')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
        _cached_existing_metadata_tickers.clear()
        _cached_ticker_metadata.clear()
