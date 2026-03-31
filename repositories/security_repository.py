import pandas as pd
from sqlalchemy import text


class SecurityRepository:
    def __init__(self, engine):
        self.engine = engine

    def seed_securities(self, rows):
        pd.DataFrame(rows).to_sql("securities", self.engine, if_exists="replace", index=False)

    def get_all(self):
        query = text("SELECT * FROM securities WHERE active = 1 ORDER BY ticker")
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn)