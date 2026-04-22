import pandas as pd
from sqlalchemy import text
from datetime import datetime

from db.sql import pandas_to_sql_kwargs, qualified_table


class InputStore:
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
        df.to_sql("security_inputs", self.engine, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine))

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'security_inputs')} WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
