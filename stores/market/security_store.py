import pandas as pd
from sqlalchemy import text

from db.schema import create_tables


class SecurityStore:
    """Persist and manage the active ETF universe stored in the securities table."""

    def __init__(self, engine):
        self.engine = engine

    def _has_primary_key_on_ticker(self) -> bool:
        query = text("PRAGMA table_info(securities)")
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()

        for row in rows:
            if row["name"] == "ticker" and int(row["pk"] or 0) == 1:
                return True
        return False

    def _ensure_schema(self):
        create_tables(self.engine)

        if self._has_primary_key_on_ticker():
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

    def replace_securities_universe(self, rows):
        self._ensure_schema()

        with self.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM securities")
            pd.DataFrame(rows).to_sql("securities", conn, if_exists="append", index=False)

    def upsert_securities(self, rows, update_existing: bool = True):
        if not rows:
            return

        self._ensure_schema()

        if update_existing:
            statement = """
            INSERT INTO securities (ticker, name, asset_class, active)
            VALUES (:ticker, :name, :asset_class, :active)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                asset_class = excluded.asset_class,
                active = excluded.active
            """
        else:
            statement = """
            INSERT INTO securities (ticker, name, asset_class, active)
            VALUES (:ticker, :name, :asset_class, :active)
            ON CONFLICT(ticker) DO NOTHING
            """

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

    def get_existing_tickers(self) -> set[str]:
        self._ensure_schema()
        with self.engine.connect() as conn:
            df = pd.read_sql(text("SELECT ticker FROM securities"), conn)
        return set(df["ticker"].tolist()) if not df.empty else set()

    def list_active_securities(self):
        query = text("SELECT * FROM securities WHERE active = 1 ORDER BY ticker")
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn)

    def delete_ticker(self, ticker: str):
        self._ensure_schema()
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM securities WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
