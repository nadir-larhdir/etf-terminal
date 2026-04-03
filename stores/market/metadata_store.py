import pandas as pd
from sqlalchemy import text
from datetime import datetime


class MetadataStore:
    """Read and write descriptive ETF metadata rows."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_metadata(self, rows):
        if not rows:
            return

        df = pd.DataFrame(rows)
        if "updated_at" not in df.columns:
            df["updated_at"] = datetime.utcnow().isoformat()

        tickers = df["ticker"].dropna().astype(str).tolist()
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM security_metadata WHERE ticker = :ticker"),
                [{"ticker": ticker} for ticker in tickers],
            )
            df.to_sql("security_metadata", conn, if_exists="append", index=False)

    def get_existing_tickers(self) -> set[str]:
        with self.engine.connect() as conn:
            df = pd.read_sql(text("SELECT ticker FROM security_metadata"), conn)
        return set(df["ticker"].tolist()) if not df.empty else set()

    def get_ticker_metadata(self, ticker: str):
        query = text(
            """
            SELECT *
            FROM security_metadata
            WHERE ticker = :ticker
            LIMIT 1
            """
        )
        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"ticker": ticker})
        return df.iloc[0].to_dict() if not df.empty else None

    def delete_ticker(self, ticker: str):
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM security_metadata WHERE ticker = :ticker"),
                {"ticker": ticker},
            )
