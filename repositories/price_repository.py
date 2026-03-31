import pandas as pd
from sqlalchemy import text


class PriceRepository:
    def __init__(self, engine):
        self.engine = engine

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM price_history WHERE ticker = :ticker"), {"ticker": ticker})
            df.to_sql("price_history", conn, if_exists="append", index=False)

    def get_price_history(self, ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
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
        df = pd.read_sql(text(query), self.engine, params=params)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        return df

    def get_snapshot(self) -> pd.DataFrame:
        query = """
        WITH ranked AS (
            SELECT *,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn,
                   LAG(close) OVER (PARTITION BY ticker ORDER BY date) AS prev_close
            FROM price_history
        )
        SELECT ticker, date, close, volume, prev_close
        FROM ranked
        WHERE rn = 1
        ORDER BY ticker
        """
        return pd.read_sql(text(query), self.engine)
