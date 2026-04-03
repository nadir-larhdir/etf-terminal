import pandas as pd
from sqlalchemy import text

from stores.query_utils import index_history_frame, latest_dates_map


class PriceStore:
    """Read and write ETF daily price history rows."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_prices(self, df: pd.DataFrame):
        if df.empty:
            return

        records = df.to_dict(orient="records")
        statement = """
        INSERT INTO price_history (
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
        """
        with self.engine.begin() as conn:
            conn.execute(text(statement), records)

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM price_history WHERE ticker = ?", (ticker,))
            df.to_sql("price_history", conn, if_exists="append", index=False)

    def get_existing_tickers(self, tickers: list[str] | None = None) -> set[str]:
        query = "SELECT DISTINCT ticker FROM price_history"
        params = {}

        if tickers:
            placeholders = ", ".join(f":ticker_{idx}" for idx in range(len(tickers)))
            query += f" WHERE ticker IN ({placeholders})"
            params = {f"ticker_{idx}": ticker for idx, ticker in enumerate(tickers)}

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        return set(df["ticker"].tolist()) if not df.empty else set()

    def get_latest_stored_dates(self, tickers: list[str] | None = None) -> dict[str, str]:
        query = """
        SELECT ticker, MAX(date) AS latest_date
        FROM price_history
        """
        params = {}

        if tickers:
            placeholders = ", ".join(f":ticker_{idx}" for idx in range(len(tickers)))
            query += f" WHERE ticker IN ({placeholders})"
            params = {f"ticker_{idx}": ticker for idx, ticker in enumerate(tickers)}

        query += " GROUP BY ticker"

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        return latest_dates_map(df, key_column="ticker")

    def get_ticker_price_history(self, ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
        query = """
        SELECT date, open, high, low, close, adj_close, volume
        FROM price_history
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

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        return index_history_frame(df)

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM price_history WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
