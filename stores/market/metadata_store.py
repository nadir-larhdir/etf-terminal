"""Read/write descriptive ETF metadata rows."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import text

from db.sql import qualified_table


class MetadataStore:
    """Persist and retrieve security metadata (issuer, duration, AUM, etc.)."""

    BASE_COLUMNS = [
        "ticker",
        "conid",
        "long_name",
        "description",
        "issuer",
        "duration",
        "benchmark_index",
        "category",
        "duration_bucket",
        "currency",
        "exchange",
        "expense_ratio",
        "total_assets",
        "quote_type",
        "source",
        "updated_at",
    ]

    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert_metadata(self, rows: list[dict]) -> None:
        """Insert or update metadata rows, aligning columns to BASE_COLUMNS."""
        if not rows:
            return
        df = pd.DataFrame(rows)
        if "updated_at" not in df.columns:
            df["updated_at"] = datetime.now(UTC).isoformat()
        for col in self.BASE_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[self.BASE_COLUMNS]
        statement = f"""
        INSERT INTO {qualified_table(self.engine, 'security_metadata')} (
            ticker, conid, long_name, description, issuer, duration,
            benchmark_index, category, duration_bucket, currency, exchange,
            expense_ratio, total_assets, quote_type, source, updated_at
        ) VALUES (
            :ticker, :conid, :long_name, :description, :issuer, :duration,
            :benchmark_index, :category, :duration_bucket, :currency, :exchange,
            :expense_ratio, :total_assets, :quote_type, :source, :updated_at
        )
        ON CONFLICT(ticker) DO UPDATE SET
            conid = excluded.conid, long_name = excluded.long_name,
            description = excluded.description, issuer = excluded.issuer,
            duration = excluded.duration, benchmark_index = excluded.benchmark_index,
            category = excluded.category, duration_bucket = excluded.duration_bucket,
            currency = excluded.currency, exchange = excluded.exchange,
            expense_ratio = excluded.expense_ratio, total_assets = excluded.total_assets,
            quote_type = excluded.quote_type, source = excluded.source,
            updated_at = excluded.updated_at
        """
        with self.engine.begin() as conn:
            conn.execute(text(statement), df.to_dict(orient="records"))

    def delete_ticker(self, ticker: str) -> None:
        """Remove the metadata row for the given ticker."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"DELETE FROM {qualified_table(self.engine, 'security_metadata')} WHERE ticker = :ticker"
                ),
                {"ticker": ticker},
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_existing_tickers(self) -> set[str]:
        """Return the set of tickers that have a metadata row."""
        return self._existing_tickers()

    def get_ticker_metadata(self, ticker: str) -> dict | None:
        """Return the metadata dict for a single ticker, or None if not found."""
        return self._ticker_metadata(ticker)

    # ------------------------------------------------------------------
    # Private query helpers
    # ------------------------------------------------------------------

    def _existing_tickers(self) -> set[str]:
        with self.engine.connect() as conn:
            df = pd.read_sql(
                text(f"SELECT ticker FROM {qualified_table(self.engine, 'security_metadata')}"),
                conn,
            )
        return set(df["ticker"].tolist()) if not df.empty else set()

    def _ticker_metadata(self, ticker: str) -> dict | None:
        query = text(f"""
            SELECT * FROM {qualified_table(self.engine, 'security_metadata')}
            WHERE ticker = :ticker LIMIT 1
        """)
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker})
        return df.iloc[0].to_dict() if not df.empty else None
