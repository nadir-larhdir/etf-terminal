import pandas as pd
from sqlalchemy import text


class PriceRepository:
    def __init__(self, engine):
        self.engine = engine

    def upsert_prices(self, df: pd.DataFrame):
        df.to_sql("price_history", self.engine, if_exists="append", index=False)

    def replace_ticker_prices(self, ticker: str, df: pd.DataFrame):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM price_history WHERE ticker = ?", (ticker,))
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

        # ✅ THIS IS THE CRITICAL FIX
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

        return df