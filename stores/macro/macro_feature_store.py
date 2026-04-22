import pandas as pd
from sqlalchemy import text

from db.sql import qualified_table
from stores.query_utils import pivot_time_series, sql_in_clause_params


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
        placeholders, params = sql_in_clause_params("feature", feature_names)
        query += f" AND feature_name IN ({placeholders})"
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

    placeholders, params = sql_in_clause_params("feature", feature_names)
    query = f"""
    WITH ranked AS (
        SELECT
            feature_name,
            date,
            value,
            category,
            sub_category,
            ROW_NUMBER() OVER (PARTITION BY feature_name ORDER BY date DESC) AS rn
        FROM {qualified_table(_engine, 'macro_features')}
        WHERE feature_name IN ({placeholders})
    )
    SELECT feature_name, date, value, category, sub_category
    FROM ranked
    WHERE rn = 1
    ORDER BY feature_name
    """

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

    def delete_features(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        query = f"DELETE FROM {qualified_table(self.engine, 'macro_features')} WHERE 1 = 1"
        params: dict[str, str] = {}
        if start_date is not None:
            query += " AND date >= :start_date"
            params["start_date"] = str(start_date)
        if end_date is not None:
            query += " AND date <= :end_date"
            params["end_date"] = str(end_date)

        with self.engine.begin() as conn:
            conn.execute(text(query), params)

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

    def get_latest_feature_date(self) -> str | None:
        query = f"SELECT MAX(date) AS latest_date FROM {qualified_table(self.engine, 'macro_features')}"
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        if df.empty or pd.isna(df.iloc[0]["latest_date"]):
            return None
        return str(df.iloc[0]["latest_date"])

    def _write_chunk_size(self, record_count: int) -> int:
        """Use smaller batches for Supabase/Postgres to avoid long single upserts."""

        if record_count <= self.DEFAULT_CHUNK_SIZE:
            return record_count
        if self.engine.dialect.name == "postgresql":
            return self.SUPABASE_CHUNK_SIZE
        return self.DEFAULT_CHUNK_SIZE
