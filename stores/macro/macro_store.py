import pandas as pd
from sqlalchemy import text

from db.sql import pandas_to_sql_kwargs, qualified_table
from stores.query_utils import index_history_frame, latest_dates_map, pivot_time_series


def _series_matrix(
    _engine,
    series_ids: tuple[str, ...] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    query = f"""
    SELECT series_id, date, value
    FROM {qualified_table(_engine, 'macro_data')}
    WHERE is_active = 1
    """
    params = {}

    if series_ids:
        placeholders = ", ".join(f":series_id_{idx}" for idx in range(len(series_ids)))
        query += f" AND series_id IN ({placeholders})"
        params.update({f"series_id_{idx}": series_id for idx, series_id in enumerate(series_ids)})
    if start_date is not None:
        query += " AND date >= :start_date"
        params["start_date"] = str(start_date)
    if end_date is not None:
        query += " AND date <= :end_date"
        params["end_date"] = str(end_date)

    with _engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params=params)

    return pivot_time_series(df, column_column="series_id")


class MacroStore:
    """Read and write macroeconomic time-series observations."""

    def __init__(self, engine):
        self.engine = engine

    def upsert_series(self, df: pd.DataFrame):
        if df.empty:
            return

        records = df.to_dict(orient="records")
        statement = """
        INSERT INTO {macro_table} (
            series_id,
            date,
            value,
            series_name,
            category,
            sub_category,
            frequency,
            units,
            source,
            is_active,
            last_updated_at
        ) VALUES (
            :series_id,
            :date,
            :value,
            :series_name,
            :category,
            :sub_category,
            :frequency,
            :units,
            :source,
            :is_active,
            :last_updated_at
        )
        ON CONFLICT(series_id, date) DO UPDATE SET
            value = excluded.value,
            series_name = excluded.series_name,
            category = excluded.category,
            sub_category = excluded.sub_category,
            frequency = excluded.frequency,
            units = excluded.units,
            source = excluded.source,
            is_active = excluded.is_active,
            last_updated_at = excluded.last_updated_at
        """.format(macro_table=qualified_table(self.engine, "macro_data"))
        with self.engine.begin() as conn:
            conn.execute(text(statement), records)
    def replace_series(self, series_id: str, df: pd.DataFrame):
        with self.engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {qualified_table(self.engine, 'macro_data')} WHERE series_id = :series_id"),
                {"series_id": series_id},
            )
            if not df.empty:
                df.to_sql("macro_data", conn, if_exists="append", index=False, **pandas_to_sql_kwargs(self.engine))

    def get_latest_stored_dates(self, series_ids: list[str] | None = None) -> dict[str, str]:
        query = f"""
        SELECT series_id, MAX(date) AS latest_date
        FROM {qualified_table(self.engine, 'macro_data')}
        """
        params = {}

        if series_ids:
            placeholders = ", ".join(f":series_id_{idx}" for idx in range(len(series_ids)))
            query += f" WHERE series_id IN ({placeholders})"
            params = {f"series_id_{idx}": series_id for idx, series_id in enumerate(series_ids)}

        query += " GROUP BY series_id"

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)

        return latest_dates_map(df, key_column="series_id")

    def get_series_history(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        query = f"""
        SELECT date, value, series_name, category, sub_category, frequency, units, source, is_active, last_updated_at
        FROM {qualified_table(self.engine, 'macro_data')}
        WHERE series_id = :series_id
        """
        params = {"series_id": series_id}

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

    def get_series_matrix(
        self,
        series_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        normalized = tuple(sorted(dict.fromkeys(series_ids))) if series_ids else None
        return _series_matrix(self.engine, normalized, start_date, end_date).copy()
