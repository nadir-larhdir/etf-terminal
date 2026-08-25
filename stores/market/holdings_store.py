"""Read/write cached daily ETF holdings snapshots."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from db.schema import create_tables
from db.sql import pandas_to_sql_kwargs, qualified_table


class HoldingsStore:
    """Persist and retrieve parsed ETF holdings snapshots."""

    BASE_COLUMNS = [
        "ticker",
        "as_of_date",
        "position",
        "name",
        "cusip",
        "isin",
        "sedol",
        "weight",
        "coupon",
        "maturity_dt",
        "price",
        "market_value",
        "face_amount",
        "source",
        "fetched_at",
    ]

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._schema_ready = False

    def replace_holdings(
        self,
        ticker: str,
        frame: pd.DataFrame,
        *,
        as_of_date: str | date | None = None,
        source: str = "provider",
    ) -> None:
        """Replace one ticker snapshot for the given date."""
        if frame.empty:
            return
        self._ensure_schema()

        snapshot_date = self._normalize_as_of_date(as_of_date)
        payload = frame.copy()
        if "weight" in payload.columns:
            payload["weight"] = pd.to_numeric(payload["weight"], errors="coerce")
            payload = payload.sort_values("weight", ascending=False, na_position="last")

        payload["ticker"] = ticker.upper()
        payload["as_of_date"] = snapshot_date
        payload["position"] = range(1, len(payload) + 1)
        payload["source"] = source
        payload["fetched_at"] = datetime.now(UTC)
        if "maturity_dt" in payload.columns:
            payload["maturity_dt"] = pd.to_datetime(payload["maturity_dt"], errors="coerce")

        for column in self.BASE_COLUMNS:
            if column not in payload.columns:
                payload[column] = None
        payload = payload[self.BASE_COLUMNS]

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"DELETE FROM {qualified_table(self.engine, 'etf_holdings')} "
                    "WHERE ticker = :ticker AND as_of_date = :as_of_date"
                ),
                {"ticker": ticker.upper(), "as_of_date": snapshot_date},
            )
            payload.to_sql(
                "etf_holdings",
                conn,
                if_exists="append",
                index=False,
                **pandas_to_sql_kwargs(self.engine),
            )

    def get_latest_holdings(self, ticker: str, limit: int | None = None) -> pd.DataFrame:
        """Return the latest cached snapshot for ticker."""
        self._ensure_schema()
        limit_clause = " LIMIT :limit" if limit is not None else ""
        params: dict[str, Any] = {"ticker": ticker.upper()}
        if limit is not None:
            params["limit"] = int(limit)
        query = text(f"""
            SELECT *
            FROM {qualified_table(self.engine, 'etf_holdings')}
            WHERE ticker = :ticker
              AND as_of_date = (
                  SELECT MAX(as_of_date)
                  FROM {qualified_table(self.engine, 'etf_holdings')}
                  WHERE ticker = :ticker
              )
            ORDER BY position
            {limit_clause}
            """)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params=params)

    def get_latest_as_of_date(self, ticker: str) -> str | None:
        """Return the latest cached holdings date for ticker."""
        self._ensure_schema()
        query = text(f"""
            SELECT MAX(as_of_date) AS as_of_date
            FROM {qualified_table(self.engine, 'etf_holdings')}
            WHERE ticker = :ticker
            """)
        with self.engine.connect() as conn:
            frame = pd.read_sql(query, conn, params={"ticker": ticker.upper()})
        if frame.empty or pd.isna(frame.iloc[0]["as_of_date"]):
            return None
        return str(frame.iloc[0]["as_of_date"])

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        create_tables(self.engine)
        self._schema_ready = True

    @staticmethod
    def _normalize_as_of_date(as_of_date: str | date | None) -> date:
        """Coerce a caller-supplied snapshot date to a `date`, defaulting to today."""
        if as_of_date is None:
            return date.today()
        if isinstance(as_of_date, date):
            return as_of_date
        return date.fromisoformat(str(pd.Timestamp(as_of_date).date()))
