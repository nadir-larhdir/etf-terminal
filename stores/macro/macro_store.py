"""Read/write macroeconomic time-series observations."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from db.sql import pandas_to_sql_kwargs, qualified_table
from stores.query_utils import (
    index_history_frame,
    latest_dates_map,
    pivot_time_series,
    sql_in_clause_params,
)


class MacroStore:
    """Persist and retrieve raw FRED macro series stored in the macro_data table."""

    def __init__(self, engine):
        self.engine = engine

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert_series(self, df: pd.DataFrame) -> None:
        """Insert or update macro observations, overwriting existing (series_id, date) pairs."""
        if df.empty:
            return
        records = self._normalize_frame_for_write(df).to_dict(orient="records")
        statement = f"""
        INSERT INTO {qualified_table(self.engine, 'macro_data')} (
            series_id, date, value, series_name, category, sub_category,
            frequency, units, source, is_active, last_updated_at
        ) VALUES (
            :series_id, :date, :value, :series_name, :category, :sub_category,
            :frequency, :units, :source, :is_active, :last_updated_at
        )
        ON CONFLICT(series_id, date) DO UPDATE SET
            value = excluded.value, series_name = excluded.series_name,
            category = excluded.category, sub_category = excluded.sub_category,
            frequency = excluded.frequency, units = excluded.units,
            source = excluded.source, is_active = excluded.is_active,
            last_updated_at = excluded.last_updated_at
        """
        with self.engine.begin() as conn:
            conn.execute(text(statement), records)

    def replace_series(self, series_id: str, df: pd.DataFrame) -> None:
        """Delete all rows for the series and insert the provided frame."""
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"DELETE FROM {qualified_table(self.engine, 'macro_data')} WHERE series_id = :series_id"
                ),
                {"series_id": series_id},
            )
            if not df.empty:
                self._normalize_frame_for_write(df).to_sql(
                    "macro_data",
                    conn,
                    if_exists="append",
                    index=False,
                    **pandas_to_sql_kwargs(self.engine),
                )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_latest_stored_dates(self, series_ids: list[str] | None = None) -> dict[str, str]:
        """Return a mapping of series_id → latest stored date string."""
        query = f"SELECT series_id, MAX(date) AS latest_date FROM {qualified_table(self.engine, 'macro_data')}"
        params: dict = {}
        if series_ids:
            placeholders, params = sql_in_clause_params("series_id", series_ids)
            query += f" WHERE series_id IN ({placeholders})"
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
        """Return a date-indexed frame of observations for a single FRED series."""
        query = f"""
        SELECT date, value, series_name, category, sub_category, frequency, units, source, is_active, last_updated_at
        FROM {qualified_table(self.engine, 'macro_data')}
        WHERE series_id = :series_id
        """
        params: dict = {"series_id": series_id}
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
        """Return a wide date × series_id matrix of active macro observations."""
        normalized = tuple(sorted(dict.fromkeys(series_ids))) if series_ids else None
        return self._series_matrix(normalized, start_date, end_date).copy()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _series_matrix(
        self,
        series_ids: tuple[str, ...] | None,
        start_date: str | None,
        end_date: str | None,
    ) -> pd.DataFrame:
        query = f"""
        SELECT series_id, date, value
        FROM {qualified_table(self.engine, 'macro_data')}
        WHERE is_active = 1
        """
        params: dict = {}
        if series_ids:
            placeholders, params = sql_in_clause_params("series_id", series_ids)
            query += f" AND series_id IN ({placeholders})"
        if start_date is not None:
            query += " AND date >= :start_date"
            params["start_date"] = str(start_date)
        if end_date is not None:
            query += " AND date <= :end_date"
            params["end_date"] = str(end_date)
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params=params)
        return pivot_time_series(df, column_column="series_id")

    @staticmethod
    def _normalize_frame_for_write(df: pd.DataFrame) -> pd.DataFrame:
        """Coerce date and last_updated_at columns to the types expected by the database."""
        normalized = df.copy()
        if "date" in normalized.columns:
            series = pd.to_datetime(normalized["date"], errors="coerce")
            normalized["date"] = series.dt.date.where(series.notna(), None)
        if "last_updated_at" in normalized.columns:
            series = pd.to_datetime(normalized["last_updated_at"], errors="coerce")
            normalized["last_updated_at"] = series.where(series.notna(), None)
        return normalized
