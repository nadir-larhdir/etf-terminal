"""Read/write the active ETF universe in the securities table."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import inspect, text

from db.schema import create_tables
from db.sql import pandas_to_sql_kwargs, qualified_table, schema_name


class SecurityStore:
    """Persist and manage the active ETF universe stored in the securities table."""

    def __init__(self, engine):
        self.engine = engine
        self._schema_ready = False

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def replace_securities_universe(self, rows: list[dict]) -> None:
        """Delete all existing securities and insert the provided rows wholesale."""
        self._ensure_schema()
        with self.engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {qualified_table(self.engine, 'securities')}"))
            pd.DataFrame(rows).to_sql(
                "securities", conn, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine)
            )

    def upsert_securities(self, rows: list[dict], update_existing: bool = True) -> None:
        """Insert securities, optionally updating name/asset_class on conflict."""
        if not rows:
            return
        self._ensure_schema()
        on_conflict = (
            "DO UPDATE SET name = excluded.name, asset_class = excluded.asset_class, active = excluded.active"
            if update_existing
            else "DO NOTHING"
        )
        statement = f"""
        INSERT INTO {qualified_table(self.engine, 'securities')} (ticker, name, asset_class, active)
        VALUES (:ticker, :name, :asset_class, :active)
        ON CONFLICT(ticker) {on_conflict}
        """
        payload = [
            {"ticker": r["ticker"], "name": r["name"], "asset_class": r["asset_class"], "active": r.get("active", 1)}
            for r in rows
        ]
        with self.engine.begin() as conn:
            conn.execute(text(statement), payload)

    def delete_ticker(self, ticker: str) -> None:
        """Remove a ticker from the securities table."""
        self._ensure_schema()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'securities')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_existing_tickers(self) -> set[str]:
        """Return the set of all tickers currently in the securities table."""
        self._ensure_schema()
        with self.engine.connect() as conn:
            df = pd.read_sql(
                text(f"SELECT ticker FROM {qualified_table(self.engine, 'securities')}"), conn
            )
        return set(df["ticker"].tolist()) if not df.empty else set()

    def list_active_securities(self) -> pd.DataFrame:
        """Return a DataFrame of all active (active=1) securities ordered by ticker."""
        self._ensure_schema()
        return self._active_securities().copy()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_securities(self) -> pd.DataFrame:
        query = text(
            f"SELECT * FROM {qualified_table(self.engine, 'securities')} WHERE active = 1 ORDER BY ticker"
        )
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn)

    def _has_primary_key_on_ticker(self) -> bool:
        """Return True if the securities table already has ticker as its primary key."""
        if self.engine.dialect.name != "sqlite":
            inspector = inspect(self.engine)
            active_schema = schema_name(self.engine)
            pk = inspector.get_pk_constraint("securities", schema=active_schema)
            return pk.get("constrained_columns") == ["ticker"]

        query = text("PRAGMA table_info(securities)")
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return any(row["name"] == "ticker" and int(row["pk"] or 0) == 1 for row in rows)

    def _ensure_schema(self) -> None:
        """Bootstrap the schema and migrate legacy tables without a ticker primary key."""
        if self._schema_ready:
            return

        create_tables(self.engine)

        if self._has_primary_key_on_ticker():
            self._schema_ready = True
            return

        # Rebuild securities table with the correct primary key constraint.
        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS securities__backup AS "
                "SELECT ticker, name, asset_class, active FROM securities"
            )
            conn.exec_driver_sql("DROP TABLE IF EXISTS securities")

        create_tables(self.engine)

        with self.engine.begin() as conn:
            conn.execute(text(f"""
                INSERT INTO {qualified_table(self.engine, 'securities')} (ticker, name, asset_class, active)
                SELECT ticker, name, asset_class, COALESCE(active, 1)
                FROM securities__backup
                WHERE ticker IS NOT NULL
                ON CONFLICT(ticker) DO UPDATE SET
                    name = excluded.name,
                    asset_class = excluded.asset_class,
                    active = excluded.active
            """))
            conn.exec_driver_sql("DROP TABLE IF EXISTS securities__backup")

        self._schema_ready = True
