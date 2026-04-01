import pandas as pd
from sqlalchemy import text
from datetime import datetime


class MetadataRepository:
    def __init__(self, engine):
        self.engine = engine

    def upsert_metadata(self, rows):
        if not rows:
            return

        df = pd.DataFrame(rows)
        if "updated_at" not in df.columns:
            df["updated_at"] = datetime.utcnow().isoformat()

        with self.engine.begin() as conn:
            for _, row in df.iterrows():
                conn.exec_driver_sql(
                    "DELETE FROM security_metadata WHERE ticker = ?",
                    (row["ticker"],),
                )
            df.to_sql("security_metadata", conn, if_exists="append", index=False)

    def get_metadata(self, ticker: str):
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