"""Read/write discretionary desk inputs (flows, notes, premium/discount)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import text

from db.sql import pandas_to_sql_kwargs, qualified_table


class InputStore:
    """Store and remove desk-level per-ticker inputs such as flows and notes."""

    def __init__(self, engine):
        self.engine = engine

    def save_inputs(
        self,
        ticker: str,
        date: str,
        flow_usd_mm: float,
        premium_discount_pct: float,
        desk_note: str,
    ) -> None:
        """Append a single desk-input row for the given ticker and date."""
        df = pd.DataFrame(
            [
                {
                    "ticker": ticker,
                    "date": date,
                    "flow_usd_mm": flow_usd_mm,
                    "premium_discount_pct": premium_discount_pct,
                    "desk_note": desk_note,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ]
        )
        df.to_sql(
            "security_inputs",
            self.engine,
            if_exists="append",
            index=False,
            **pandas_to_sql_kwargs(self.engine),
        )

    def delete_ticker(self, ticker: str) -> None:
        """Remove all desk-input rows for the given ticker."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"DELETE FROM {qualified_table(self.engine, 'security_inputs')} WHERE ticker = :ticker"
                ),
                {"ticker": ticker},
            )
