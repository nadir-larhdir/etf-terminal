from __future__ import annotations


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
