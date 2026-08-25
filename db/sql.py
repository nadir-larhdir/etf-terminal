from __future__ import annotations

from typing import Any

from sqlalchemy.engine import Engine

from config import APP_ENV, DATA_BACKEND, DB_SCHEMA


def schema_name(engine: Engine) -> str | None:
    if engine.dialect.name != "postgresql":
        return None
    return str(engine.get_execution_options().get("schema_name") or "public")


def qualified_table(engine: Engine, table_name: str) -> str:
    schema = schema_name(engine)
    return f'"{schema}"."{table_name}"' if schema else table_name


def pandas_to_sql_kwargs(engine: Engine) -> dict[str, Any]:
    schema = schema_name(engine)
    return {"schema": schema} if schema else {}


def cache_scope(engine: Engine) -> str:
    """Build a stable cache namespace so env/backend mixes cannot bleed across runs."""

    return f"{DATA_BACKEND}:{APP_ENV}:{DB_SCHEMA}:{engine.url}"
