from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool, QueuePool

from config import APP_ENV, DATA_BACKEND, DB_PATH, DB_SCHEMA, DATABASE_URL


def _sqlite_url(app_env: str) -> str:
    return f"sqlite:///{DB_PATH.parent / f'market_data_{app_env}.db'}"


def _supabase_connect_args(schema_name: str) -> dict:
    return {"options": f"-csearch_path={schema_name}"}


def _normalize_postgres_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _ensure_sslmode(database_url: str) -> str:
    if "sslmode=" in database_url:
        return database_url
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}sslmode=require"


def _is_supabase_pooler_url(database_url: str) -> bool:
    return "pooler.supabase.com" in database_url


def _uses_session_pooler(database_url: str) -> bool:
    return _is_supabase_pooler_url(database_url) and ":5432/" in database_url


def get_engine(*, data_backend: str | None = None, app_env: str | None = None, database_url: str | None = None):
    backend = (data_backend or DATA_BACKEND).strip().lower()
    env = (app_env or APP_ENV).strip().lower()
    resolved_url = database_url or DATABASE_URL

    if backend == "local" or not resolved_url:
        return create_engine(_sqlite_url(env), future=True).execution_options(schema_name=None)

    normalized_url = _ensure_sslmode(_normalize_postgres_url(resolved_url))
    engine_kwargs = {
        "future": True,
        "connect_args": _supabase_connect_args(DB_SCHEMA),
        "pool_pre_ping": True,
    }
    if _uses_session_pooler(normalized_url):
        engine_kwargs.update({"poolclass": QueuePool, "pool_size": 2, "max_overflow": 2, "pool_recycle": 1800})
    elif _is_supabase_pooler_url(normalized_url):
        engine_kwargs["poolclass"] = NullPool

    engine = create_engine(normalized_url, **engine_kwargs)
    return engine.execution_options(schema_name=DB_SCHEMA)
