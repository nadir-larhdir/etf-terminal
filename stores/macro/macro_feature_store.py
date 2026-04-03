import pandas as pd
from sqlalchemy import text

from stores.query_utils import index_history_frame, pivot_time_series


class MacroFeatureStore:
    """Read and write derived macro feature time series."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_features(self, df: pd.DataFrame):
        if df.empty:
            return

        records = df.to_dict(orient="records")
        statement = """
        INSERT INTO macro_features (
            feature_name,
            date,
            value,
            category,
            sub_category,
            source,
            last_updated_at
        ) VALUES (
            :feature_name,
            :date,
            :value,
            :category,
            :sub_category,
            :source,
            :last_updated_at
        )
        ON CONFLICT(feature_name, date) DO UPDATE SET
            value = excluded.value,
            category = excluded.category,
            sub_category = excluded.sub_category,
            source = excluded.source,
            last_updated_at = excluded.last_updated_at
        """
        with self.engine.begin() as conn:
            conn.execute(text(statement), records)

    def get_feature_history(
        self,
        feature_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        query = """
        SELECT date, value, category, sub_category, source, last_updated_at
        FROM macro_features
        WHERE feature_name = :feature_name
        """
        params = {"feature_name": feature_name}

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

    def get_feature_matrix(self, feature_names: list[str] | None = None) -> pd.DataFrame:
        query = """
        SELECT feature_name, date, value
        FROM macro_features
        """
        params = {}
        if feature_names:
            placeholders = ", ".join(f":feature_{idx}" for idx in range(len(feature_names)))
            query += f" WHERE feature_name IN ({placeholders})"
            params = {f"feature_{idx}": name for idx, name in enumerate(feature_names)}

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        return pivot_time_series(df, column_column="feature_name")

    def get_latest_feature_values(self, feature_names: list[str]) -> pd.DataFrame:
        if not feature_names:
            return pd.DataFrame(columns=["feature_name", "date", "value"])

        placeholders = ", ".join(f":feature_{idx}" for idx in range(len(feature_names)))
        query = f"""
        WITH ranked AS (
            SELECT
                feature_name,
                date,
                value,
                category,
                sub_category,
                ROW_NUMBER() OVER (PARTITION BY feature_name ORDER BY date DESC) AS rn
            FROM macro_features
            WHERE feature_name IN ({placeholders})
        )
        SELECT feature_name, date, value, category, sub_category
        FROM ranked
        WHERE rn = 1
        ORDER BY feature_name
        """
        params = {f"feature_{idx}": name for idx, name in enumerate(feature_names)}

        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params)

    def get_feature_counts(self) -> pd.DataFrame:
        query = """
        SELECT feature_name, COUNT(*) AS row_count
        FROM macro_features
        GROUP BY feature_name
        ORDER BY feature_name
        """
        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn)
