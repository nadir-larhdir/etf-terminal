from __future__ import annotations

from config import APP_ENV, DATA_BACKEND, DB_SCHEMA


def schema_name(engine) -> str | None:
    if engine.dialect.name != "postgresql":
        return None
    return engine.get_execution_options().get("schema_name") or "public"


def qualified_table(engine, table_name: str) -> str:
    schema = schema_name(engine)
    return f'"{schema}"."{table_name}"' if schema else table_name


def pandas_to_sql_kwargs(engine) -> dict:
    schema = schema_name(engine)
    return {"schema": schema} if schema else {}


def cache_scope(engine) -> str:
    """Build a stable cache namespace so env/backend mixes cannot bleed across runs."""

    return f"{DATA_BACKEND}:{APP_ENV}:{DB_SCHEMA}:{engine.url}"
