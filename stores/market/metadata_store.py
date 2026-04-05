import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime

from db.sql import cache_scope, qualified_table


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

        records = df.to_dict(orient="records")
        statement = """
        INSERT INTO {metadata_table} (
            ticker,
            conid,
            long_name,
            description,
            issuer,
            benchmark_index,
            category,
            duration_bucket,
            currency,
            exchange,
            expense_ratio,
            total_assets,
            quote_type,
            source,
            updated_at
        ) VALUES (
            :ticker,
            :conid,
            :long_name,
            :description,
            :issuer,
            :benchmark_index,
            :category,
            :duration_bucket,
            :currency,
            :exchange,
            :expense_ratio,
            :total_assets,
            :quote_type,
            :source,
            :updated_at
        )
        ON CONFLICT(ticker) DO UPDATE SET
            conid = excluded.conid,
            long_name = excluded.long_name,
            description = excluded.description,
            issuer = excluded.issuer,
            benchmark_index = excluded.benchmark_index,
            category = excluded.category,
            duration_bucket = excluded.duration_bucket,
            currency = excluded.currency,
            exchange = excluded.exchange,
            expense_ratio = excluded.expense_ratio,
            total_assets = excluded.total_assets,
            quote_type = excluded.quote_type,
            source = excluded.source,
            updated_at = excluded.updated_at
        """.format(metadata_table=qualified_table(self.engine, "security_metadata"))

        with self.engine.begin() as conn:
            conn.execute(text(statement), records)
        _cached_existing_metadata_tickers.clear()
        _cached_ticker_metadata.clear()

    def get_existing_tickers(self) -> set[str]:
        return _cached_existing_metadata_tickers(cache_scope(self.engine), self.engine)

    def get_ticker_metadata(self, ticker: str):
        return _cached_ticker_metadata(cache_scope(self.engine), self.engine, ticker)

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'security_metadata')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
        _cached_existing_metadata_tickers.clear()
        _cached_ticker_metadata.clear()
