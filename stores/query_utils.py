"""Small helpers for shaping database query results into app-friendly objects."""

from typing import Any, cast

import pandas as pd

from fixed_income.series import as_text


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return a frame's rows as dicts keyed by column name.

    `to_dict(orient="records")` is typed as `Hashable`-keyed because a column label can
    be any hashable; every frame written here has string columns, so narrow it once
    rather than casting at each call site.
    """
    return cast(list[dict[str, Any]], df.to_dict(orient="records"))


def sql_in_clause_params(
    prefix: str, items: tuple[str, ...] | list[str]
) -> tuple[str, dict[str, str]]:
    """Build named SQL placeholders and params for a small IN-clause list."""

    values = list(items)
    placeholders = ", ".join(f":{prefix}_{idx}" for idx in range(len(values)))
    params = {f"{prefix}_{idx}": value for idx, value in enumerate(values)}
    return placeholders, params


def append_date_filters(
    query: str,
    params: dict[str, Any],
    *,
    start_date: object = None,
    end_date: object = None,
    column: str = "date",
) -> tuple[str, dict[str, Any]]:
    """Append optional inclusive date filters to a SQL query and params dict."""
    if start_date is not None:
        query += f" AND {column} >= :start_date"
        params["start_date"] = str(start_date)
    if end_date is not None:
        query += f" AND {column} <= :end_date"
        params["end_date"] = str(end_date)
    return query, params


def latest_date_query(table: str, key_column: str) -> str:
    """Build a grouped latest-date SQL query for table/key pairs."""
    return f"SELECT {key_column}, MAX(date) AS latest_date FROM {table}"


def latest_dates_map(
    df: pd.DataFrame, *, key_column: str, date_column: str = "latest_date"
) -> dict[str, str]:
    """Convert grouped latest-date query results into a simple string mapping."""
    if df.empty:
        return {}

    latest = df.dropna(subset=[date_column]).copy()
    return dict(
        zip(
            as_text(latest[key_column]).tolist(),
            as_text(latest[date_column]).tolist(),
            strict=False,
        )
    )


def index_history_frame(df: pd.DataFrame, *, date_column: str = "date") -> pd.DataFrame:
    """Convert a raw query result with a date column into a date-indexed frame."""
    if df.empty:
        return df

    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])
    return df.set_index(date_column)


def pivot_time_series(
    df: pd.DataFrame,
    *,
    index_column: str = "date",
    column_column: str,
    value_column: str = "value",
) -> pd.DataFrame:
    """Pivot long-form time-series rows into a wide matrix sorted by date."""
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    working[index_column] = pd.to_datetime(working[index_column])
    matrix = working.pivot(
        index=index_column, columns=column_column, values=value_column
    ).sort_index()
    matrix.columns.name = None
    return matrix
