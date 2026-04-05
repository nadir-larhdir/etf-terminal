import pandas as pd
import streamlit as st
from sqlalchemy import inspect
from sqlalchemy import text

from db.schema import create_tables
from db.sql import cache_scope, pandas_to_sql_kwargs, qualified_table, schema_name


@st.cache_data(ttl=900, show_spinner=False)
def _cached_active_securities(_cache_key: str, _engine) -> pd.DataFrame:
    query = text(f"SELECT * FROM {qualified_table(_engine, 'securities')} WHERE active = 1 ORDER BY ticker")
    with _engine.connect() as conn:
        return pd.read_sql(query, conn)


class SecurityStore:
    """Persist and manage the active ETF universe stored in the securities table."""

    def __init__(self, engine):
        self.engine = engine
        self._schema_ready = False

    def _has_primary_key_on_ticker(self) -> bool:
        if self.engine.dialect.name != "sqlite":
            inspector = inspect(self.engine)
            active_schema = schema_name(self.engine)
            columns = inspector.get_columns("securities", schema=active_schema)
            primary_key = inspector.get_pk_constraint("securities", schema=active_schema)
            pk_columns = primary_key.get("constrained_columns") or []
            return pk_columns == ["ticker"] and any(column["name"] == "ticker" for column in columns)

        query = text("PRAGMA table_info(securities)")
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()

        for row in rows:
            if row["name"] == "ticker" and int(row["pk"] or 0) == 1:
                return True
        return False

    def _ensure_schema(self):
        if self._schema_ready:
            return

        create_tables(self.engine)

        if self._has_primary_key_on_ticker():
            self._schema_ready = True
            return

        with self.engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS securities__backup AS
                SELECT ticker, name, asset_class, active
                FROM securities
                """
            )
            conn.exec_driver_sql("DROP TABLE IF EXISTS securities")

        create_tables(self.engine)

        restore_statement = text(
            """
            INSERT INTO securities (ticker, name, asset_class, active)
            SELECT ticker, name, asset_class, COALESCE(active, 1)
            FROM securities__backup
            WHERE ticker IS NOT NULL
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                asset_class = excluded.asset_class,
                active = excluded.active
            """
        )
        with self.engine.begin() as conn:
            conn.execute(restore_statement)
            conn.exec_driver_sql("DROP TABLE IF EXISTS securities__backup")
        self._schema_ready = True

    def replace_securities_universe(self, rows):
        self._ensure_schema()

        with self.engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {qualified_table(self.engine, 'securities')}"))
            pd.DataFrame(rows).to_sql("securities", conn, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine))
        _cached_active_securities.clear()

    def upsert_securities(self, rows, update_existing: bool = True):
        if not rows:
            return

        self._ensure_schema()

        if update_existing:
            statement = """
            INSERT INTO {securities_table} (ticker, name, asset_class, active)
            VALUES (:ticker, :name, :asset_class, :active)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                asset_class = excluded.asset_class,
                active = excluded.active
            """.format(securities_table=qualified_table(self.engine, "securities"))
        else:
            statement = """
            INSERT INTO {securities_table} (ticker, name, asset_class, active)
            VALUES (:ticker, :name, :asset_class, :active)
            ON CONFLICT(ticker) DO NOTHING
            """.format(securities_table=qualified_table(self.engine, "securities"))

        payload = [
            {
                "ticker": row["ticker"],
                "name": row["name"],
                "asset_class": row["asset_class"],
                "active": row.get("active", 1),
            }
            for row in rows
        ]

        with self.engine.begin() as conn:
            conn.execute(text(statement), payload)
        _cached_active_securities.clear()

    def get_existing_tickers(self) -> set[str]:
        self._ensure_schema()
        with self.engine.connect() as conn:
            df = pd.read_sql(text(f"SELECT ticker FROM {qualified_table(self.engine, 'securities')}"), conn)
        return set(df["ticker"].tolist()) if not df.empty else set()

    def list_active_securities(self):
        self._ensure_schema()
        return _cached_active_securities(cache_scope(self.engine), self.engine).copy()

    def delete_ticker(self, ticker: str):
        self._ensure_schema()
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'securities')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
        _cached_active_securities.clear()
