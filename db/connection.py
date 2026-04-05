from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from config import APP_ENV, DATA_BACKEND, DB_PATH, DB_SCHEMA, SUPABASE_DB_URL


def _sqlite_url(app_env: str) -> str:
    return f"sqlite:///{DB_PATH.parent / f'market_data_{app_env}.db'}"


def _supabase_connect_args(schema_name: str) -> dict:
    return {"options": f"-csearch_path={schema_name}"}


def _normalize_postgres_url(database_url: str) -> str:
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


def get_engine(*, data_backend: str | None = None, app_env: str | None = None):
    backend = (data_backend or DATA_BACKEND).strip().lower()
    env = (app_env or APP_ENV).strip().lower()

    if backend == "local":
        return create_engine(_sqlite_url(env), future=True).execution_options(schema_name=None)

    if not SUPABASE_DB_URL:
        raise RuntimeError(
            "SUPABASE_DB_URL is not configured. Set it in .env or use DATA_BACKEND=local."
        )

    normalized_url = _ensure_sslmode(SUPABASE_DB_URL)
    engine_kwargs = {
        "future": True,
        "connect_args": _supabase_connect_args(DB_SCHEMA),
    }
    if _is_supabase_pooler_url(normalized_url):
        engine_kwargs["poolclass"] = NullPool

    engine = create_engine(normalized_url, **engine_kwargs)
    return engine.execution_options(schema_name=DB_SCHEMA)
