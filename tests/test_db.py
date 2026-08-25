"""Engine construction, SQL qualification, and schema migration behaviour."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from db.connection import get_engine
from db.schema import create_tables, get_existing_tables
from db.sql import cache_scope, pandas_to_sql_kwargs, qualified_table, schema_name

EXPECTED_TABLES = {
    "etf_universe",
    "etf_metadata",
    "etf_holdings",
    "price_history",
    "macro_data",
    "macro_features",
    "analytics_snapshots",
}


# ── engine selection ────────────────────────────────────────────────────────


def test_the_local_backend_always_resolves_to_sqlite() -> None:
    engine = get_engine(data_backend="local", app_env="uat")

    assert engine.dialect.name == "sqlite"
    assert "market_data_uat" in str(engine.url)


def test_each_environment_gets_its_own_sqlite_file() -> None:
    uat = get_engine(data_backend="local", app_env="uat")
    prod = get_engine(data_backend="local", app_env="prod")

    assert str(uat.url) != str(prod.url)


def test_supabase_falls_back_to_sqlite_when_no_url_is_configured(monkeypatch) -> None:
    monkeypatch.setattr("db.connection.DATABASE_URL", "")

    engine = get_engine(data_backend="supabase", app_env="uat", database_url="")

    assert engine.dialect.name == "sqlite"


@pytest.mark.parametrize(
    "url",
    [
        "postgres://user:pw@host:5432/db",
        "postgresql://user:pw@host:5432/db",
        "postgresql+psycopg2://user:pw@host:5432/db",
    ],
)
def test_legacy_postgres_urls_are_rewritten_to_the_psycopg3_driver(url: str) -> None:
    engine = get_engine(data_backend="supabase", app_env="uat", database_url=url)

    assert engine.url.drivername == "postgresql+psycopg"


def test_ssl_is_required_when_the_url_does_not_ask_for_it() -> None:
    engine = get_engine(
        data_backend="supabase", app_env="uat", database_url="postgresql://u:p@host:5432/db"
    )

    assert engine.url.query.get("sslmode") == "require"


def test_an_explicit_sslmode_is_left_alone() -> None:
    engine = get_engine(
        data_backend="supabase",
        app_env="uat",
        database_url="postgresql://u:p@host:5432/db?sslmode=disable",
    )

    assert engine.url.query.get("sslmode") == "disable"


def test_the_session_pooler_gets_a_bounded_connection_pool() -> None:
    engine = get_engine(
        data_backend="supabase",
        app_env="uat",
        database_url="postgresql://u:p@aws-1.pooler.supabase.com:5432/postgres",
    )

    assert type(engine.pool).__name__ == "QueuePool"
    assert engine.pool.size() == 2  # type: ignore[attr-defined]


def test_the_transaction_pooler_holds_no_pool_of_its_own() -> None:
    engine = get_engine(
        data_backend="supabase",
        app_env="uat",
        database_url="postgresql://u:p@aws-1.pooler.supabase.com:6543/postgres",
    )

    assert type(engine.pool).__name__ == "NullPool"


# ── SQL qualification ───────────────────────────────────────────────────────


def test_sqlite_tables_are_referenced_unqualified() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    assert schema_name(engine) is None
    assert qualified_table(engine, "price_history") == "price_history"
    assert pandas_to_sql_kwargs(engine) == {}


def test_the_cache_scope_separates_backends_and_environments() -> None:
    uat = get_engine(data_backend="local", app_env="uat")
    prod = get_engine(data_backend="local", app_env="prod")

    assert cache_scope(uat) != cache_scope(prod)


# ── schema ──────────────────────────────────────────────────────────────────


def test_creating_the_schema_produces_every_core_table() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    create_tables(engine)

    assert EXPECTED_TABLES <= get_existing_tables(engine)


def test_creating_the_schema_twice_is_safe() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)

    create_tables(engine)
    create_tables(engine)

    assert EXPECTED_TABLES <= get_existing_tables(engine)


def test_a_fresh_database_reports_no_tables() -> None:
    assert get_existing_tables(create_engine("sqlite:///:memory:", future=True)) == set()


def test_price_history_is_keyed_on_ticker_and_date() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    create_tables(engine)

    row = {
        "ticker": "IEF",
        "date": "2024-01-02",
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "adj_close": 1.0,
        "volume": 1,
    }
    statement = text(
        "INSERT INTO price_history (ticker, date, open, high, low, close, adj_close, volume) "
        "VALUES (:ticker, :date, :open, :high, :low, :close, :adj_close, :volume)"
    )
    with engine.begin() as conn:
        conn.execute(statement, row)
        with pytest.raises(Exception):  # noqa: B017 - any integrity error proves the constraint
            conn.execute(statement, row)


def test_legacy_securities_tables_are_renamed_on_migration() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE securities ("
                "ticker TEXT PRIMARY KEY, name TEXT, asset_class TEXT, active INTEGER DEFAULT 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO securities (ticker, name, asset_class) VALUES ('IEF', 'iShares', 'UST')"
            )
        )

    create_tables(engine)

    tables = get_existing_tables(engine)
    assert "etf_universe" in tables and "securities" not in tables
    with engine.connect() as conn:
        assert conn.execute(text("SELECT ticker FROM etf_universe")).scalar() == "IEF"


def test_the_analytics_snapshot_table_carries_the_model_provenance_columns() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    create_tables(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("analytics_snapshots")}

    assert {"model_version", "computed_from_start_date", "computed_from_end_date"} <= columns
