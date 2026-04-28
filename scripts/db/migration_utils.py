"""Shared helpers for cross-backend database migration: copy, normalize, and prepare tables."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from config.config import ENV_DB_FILENAMES
from db.schema import TABLE_DEFINITIONS, create_tables
from db.sql import pandas_to_sql_kwargs, qualified_table

TABLE_COPY_ORDER = list(TABLE_DEFINITIONS.keys())

DATE_COLUMNS = {
    "price_history": ["date"],
    "security_inputs": ["date"],
    "macro_data": ["date"],
    "macro_features": ["date"],
    "analytics_snapshots": ["as_of_date", "computed_from_start_date", "computed_from_end_date"],
}

TIMESTAMP_COLUMNS = {
    "macro_data": ["last_updated_at"],
    "macro_features": ["last_updated_at"],
    "analytics_snapshots": ["updated_at"],
}


def parse_local_env(raw_value: str, *, label: str) -> str:
    """Validate and return a local environment name (prod or uat); raise SystemExit if invalid."""
    selected = raw_value.strip().lower()
    if selected not in ENV_DB_FILENAMES:
        raise SystemExit(
            f"Invalid {label} environment. Use --{label}-env prod or --{label}-env uat."
        )
    return selected


def truncate_target_tables(engine) -> None:
    """Delete all rows from every managed table in dependency-safe reverse order."""
    with engine.begin() as conn:
        for table_name in reversed(TABLE_COPY_ORDER):
            conn.execute(text(f"DELETE FROM {qualified_table(engine, table_name)}"))


def normalize_frame_for_target(frame: pd.DataFrame, table_name: str) -> pd.DataFrame:
    """Coerce date and timestamp columns for cross-backend compatibility."""
    normalized = frame.copy()

    for column in DATE_COLUMNS.get(table_name, []):
        if column not in normalized.columns:
            continue
        series = pd.to_datetime(normalized[column], errors="coerce")
        normalized[column] = series.dt.date.where(series.notna(), None)

    for column in TIMESTAMP_COLUMNS.get(table_name, []):
        if column not in normalized.columns:
            continue
        series = pd.to_datetime(normalized[column], errors="coerce")
        normalized[column] = series.where(series.notna(), None)

    return normalized


def copy_table(
    source_engine, target_engine, table_name: str, *, normalize_for_target: bool = False
) -> int:
    """Append all rows from source table into the matching target table; return row count."""
    source_table = qualified_table(source_engine, table_name)
    with source_engine.connect() as source_conn:
        frame = pd.read_sql(text(f"SELECT * FROM {source_table}"), source_conn)

    if frame.empty:
        return 0

    if normalize_for_target:
        frame = normalize_frame_for_target(frame, table_name)

    with target_engine.begin() as target_conn:
        frame.to_sql(
            table_name,
            target_conn,
            if_exists="append",
            index=False,
            **pandas_to_sql_kwargs(target_engine),
        )
    return len(frame)


def prepare_target(engine) -> None:
    """Ensure all tables exist on the target engine and purge any existing rows."""
    create_tables(engine)
    truncate_target_tables(engine)
