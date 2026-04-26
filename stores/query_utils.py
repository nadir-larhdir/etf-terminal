"""Small helpers for shaping database query results into app-friendly objects."""

import pandas as pd


def sql_in_clause_params(
    prefix: str, items: tuple[str, ...] | list[str]
) -> tuple[str, dict[str, str]]:
    """Build named SQL placeholders and params for a small IN-clause list."""

    values = list(items)
    placeholders = ", ".join(f":{prefix}_{idx}" for idx in range(len(values)))
    params = {f"{prefix}_{idx}": value for idx, value in enumerate(values)}
    return placeholders, params


def latest_dates_map(
    df: pd.DataFrame, *, key_column: str, date_column: str = "latest_date"
) -> dict[str, str]:
    """Convert grouped latest-date query results into a simple string mapping."""
    if df.empty:
        return {}

    latest = df.dropna(subset=[date_column]).copy()
    return dict(
        zip(
            latest[key_column].astype(str),
            latest[date_column].astype(str),
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
