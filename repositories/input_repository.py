from datetime import date, datetime
import pandas as pd
from sqlalchemy import text


class InputRepository:
    def __init__(self, engine):
        self.engine = engine

    def upsert_inputs(self, ticker: str, as_of_date: str | None, flow_usd_mm: float, premium_discount_pct: float, desk_note: str):
        if as_of_date is None:
            as_of_date = date.today().isoformat()
        payload = pd.DataFrame([
            {
                "ticker": ticker,
                "date": as_of_date,
                "flow_usd_mm": flow_usd_mm,
                "premium_discount_pct": premium_discount_pct,
                "desk_note": desk_note,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ])
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM security_inputs WHERE ticker = :ticker AND date = :date"),
                {"ticker": ticker, "date": as_of_date},
            )
            payload.to_sql("security_inputs", conn, if_exists="append", index=False)

    def get_latest_inputs(self, ticker: str) -> dict:
        query = text("""
        SELECT ticker, date, flow_usd_mm, premium_discount_pct, desk_note
        FROM security_inputs
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT 1
        """)
        df = pd.read_sql(query, self.engine, params={"ticker": ticker})
        if df.empty:
            return {
                "ticker": ticker,
                "date": None,
                "flow_usd_mm": 0.0,
                "premium_discount_pct": 0.0,
                "desk_note": "",
            }
        return df.iloc[0].to_dict()
