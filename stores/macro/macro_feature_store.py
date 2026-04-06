import pandas as pd
from sqlalchemy import text

from db.sql import qualified_table
from stores.query_utils import index_history_frame, pivot_time_series


def _feature_matrix(
    _engine,
    feature_names: tuple[str, ...] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    query = f"""
    SELECT feature_name, date, value
    FROM {qualified_table(_engine, 'macro_features')}
    WHERE 1 = 1
    """
    params = {}
    if feature_names:
        placeholders = ", ".join(f":feature_{idx}" for idx in range(len(feature_names)))
        query += f" AND feature_name IN ({placeholders})"
        params.update({f"feature_{idx}": name for idx, name in enumerate(feature_names)})
    if start_date is not None:
        query += " AND date >= :start_date"
        params["start_date"] = str(start_date)
    if end_date is not None:
        query += " AND date <= :end_date"
        params["end_date"] = str(end_date)

    with _engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    return pivot_time_series(df, column_column="feature_name")


def _latest_feature_values(_engine, feature_names: tuple[str, ...]) -> pd.DataFrame:
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
    """.replace("FROM macro_features", f"FROM {qualified_table(_engine, 'macro_features')}")
    params = {f"feature_{idx}": name for idx, name in enumerate(feature_names)}

    with _engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params)


class MacroFeatureStore:
    """Read and write derived macro feature time series."""

    SUPABASE_CHUNK_SIZE = 2_000
    DEFAULT_CHUNK_SIZE = 10_000

    def __init__(self, engine):
        self.engine = engine

    def upsert_features(self, df: pd.DataFrame):
        if df.empty:
            return

        records = df.to_dict(orient="records")
        statement = """
        INSERT INTO {feature_table} (
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
        """.format(feature_table=qualified_table(self.engine, "macro_features"))
        chunk_size = self._write_chunk_size(len(records))
        with self.engine.begin() as conn:
            for start in range(0, len(records), chunk_size):
                conn.execute(text(statement), records[start : start + chunk_size])

    def get_feature_history(
        self,
        feature_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        query = f"""
        SELECT date, value, category, sub_category, source, last_updated_at
        FROM {qualified_table(self.engine, 'macro_features')}
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

    def get_feature_matrix(
        self,
        feature_names: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        normalized = tuple(sorted(dict.fromkeys(feature_names))) if feature_names else None
        return _feature_matrix(self.engine, normalized, start_date, end_date).copy()

    def get_latest_feature_values(self, feature_names: list[str]) -> pd.DataFrame:
        normalized = tuple(sorted(dict.fromkeys(feature_names)))
        return _latest_feature_values(self.engine, normalized).copy()

    def get_feature_counts(self) -> pd.DataFrame:
        query = f"""
        SELECT feature_name, COUNT(*) AS row_count
        FROM {qualified_table(self.engine, 'macro_features')}
        GROUP BY feature_name
        ORDER BY feature_name
        """
        with self.engine.connect() as conn:
            return pd.read_sql(text(query), conn)

    def _write_chunk_size(self, record_count: int) -> int:
        """Use smaller batches for Supabase/Postgres to avoid long single upserts."""

        if record_count <= self.DEFAULT_CHUNK_SIZE:
            return record_count
        if self.engine.dialect.name == "postgresql":
            return self.SUPABASE_CHUNK_SIZE
        return self.DEFAULT_CHUNK_SIZE
