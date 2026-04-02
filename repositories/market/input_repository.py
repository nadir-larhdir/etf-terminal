import pandas as pd
from sqlalchemy import text
from datetime import datetime


class InputRepository:
    """Store discretionary desk inputs such as flows, notes, and premium discounts."""

    def __init__(self, engine):
        self.engine = engine

    def save_inputs(self, ticker: str, date: str, flow_usd_mm: float, premium_discount_pct: float, desk_note: str):
        df = pd.DataFrame([
            {
                "ticker": ticker,
                "date": date,
                "flow_usd_mm": flow_usd_mm,
                "premium_discount_pct": premium_discount_pct,
                "desk_note": desk_note,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ])
        df.to_sql("security_inputs", self.engine, if_exists="append", index=False)

    def get_latest_inputs(self, ticker: str):
        query = text("""
            SELECT *
            FROM security_inputs
            WHERE ticker = :ticker
            ORDER BY date DESC
            LIMIT 1
        """)
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker})

        return df.iloc[0].to_dict() if not df.empty else None

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM security_inputs WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
