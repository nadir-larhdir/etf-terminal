"""Database schema definitions, table creation, and incremental migration helpers."""

from sqlalchemy import inspect, text

from db.sql import qualified_table, schema_name as active_schema_name

TABLE_DEFINITIONS = {
    "securities": """
        CREATE TABLE IF NOT EXISTS securities (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            asset_class TEXT,
            active INTEGER DEFAULT 1
        )
    """,
    "price_history": """
        CREATE TABLE IF NOT EXISTS price_history (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adj_close REAL,
            volume REAL,
            source TEXT,
            updated_at TEXT,
            PRIMARY KEY (ticker, date)
        )
    """,
    "security_inputs": """
        CREATE TABLE IF NOT EXISTS security_inputs (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            flow_usd_mm REAL DEFAULT 0,
            premium_discount_pct REAL DEFAULT 0,
            desk_note TEXT DEFAULT '',
            updated_at TEXT,
            PRIMARY KEY (ticker, date)
        )
    """,
    "security_metadata": """
        CREATE TABLE IF NOT EXISTS security_metadata (
            ticker TEXT PRIMARY KEY,
            conid TEXT,
            long_name TEXT,
            description TEXT,
            issuer TEXT,
            duration REAL,
            benchmark_index TEXT,
            category TEXT,
            duration_bucket TEXT,
            currency TEXT,
            exchange TEXT,
            expense_ratio REAL,
            total_assets REAL,
            quote_type TEXT,
            source TEXT,
            updated_at TEXT
        )
    """,
    "macro_data": """
        CREATE TABLE IF NOT EXISTS macro_data (
            series_id TEXT NOT NULL,
            date DATE NOT NULL,
            value REAL,
            series_name TEXT,
            category TEXT,
            sub_category TEXT,
            frequency TEXT,
            units TEXT,
            source TEXT DEFAULT 'fred',
            is_active INTEGER DEFAULT 1,
            last_updated_at TIMESTAMP,
            PRIMARY KEY (series_id, date)
        )
    """,
    "macro_features": """
        CREATE TABLE IF NOT EXISTS macro_features (
            feature_name TEXT NOT NULL,
            date DATE NOT NULL,
            value REAL,
            category TEXT,
            sub_category TEXT,
            source TEXT DEFAULT 'derived',
            last_updated_at TIMESTAMP,
            PRIMARY KEY (feature_name, date)
        )
    """,
    "analytics_snapshots": """
        CREATE TABLE IF NOT EXISTS analytics_snapshots (
            symbol TEXT NOT NULL,
            as_of_date DATE NOT NULL,
            asset_bucket TEXT,
            benchmark_used TEXT,
            spread_proxy_used TEXT,
            estimated_duration REAL,
            rate_dv01_per_share REAL,
            benchmark_beta REAL,
            cs01_proxy_per_share REAL,
            spread_beta_per_bp REAL,
            equity_beta REAL,
            rate_model_r2 REAL,
            spread_model_r2 REAL,
            confidence_level TEXT,
            model_type TEXT,
            rate_proxy_used TEXT,
            model_version TEXT,
            computed_from_start_date DATE,
            computed_from_end_date DATE,
            notes TEXT,
            reason TEXT,
            lookback_days_used INTEGER,
            observations_used INTEGER,
            updated_at TIMESTAMP,
            PRIMARY KEY (symbol, as_of_date)
        )
    """,
}

EXPECTED_MACRO_DATA_COLUMNS = [
    "series_id", "date", "value", "series_name", "category",
    "sub_category", "frequency", "units", "source", "is_active", "last_updated_at",
]

INDEX_DEFINITIONS = {
    "idx_price_history_date": "CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history (date)",
    "idx_price_history_ticker_date": "CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date ON price_history (ticker, date)",
    "idx_macro_data_date": "CREATE INDEX IF NOT EXISTS idx_macro_data_date ON macro_data (date)",
    "idx_macro_data_series_date": "CREATE INDEX IF NOT EXISTS idx_macro_data_series_date ON macro_data (series_id, date)",
    "idx_macro_features_date": "CREATE INDEX IF NOT EXISTS idx_macro_features_date ON macro_features (date)",
    "idx_macro_features_feature_date": "CREATE INDEX IF NOT EXISTS idx_macro_features_feature_date ON macro_features (feature_name, date)",
    "idx_analytics_snapshots_symbol_date": "CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_symbol_date ON analytics_snapshots (symbol, as_of_date)",
    "idx_securities_active_ticker": "CREATE INDEX IF NOT EXISTS idx_securities_active_ticker ON securities (active, ticker)",
}


def get_existing_tables(engine) -> set[str]:
    """Return the set of table names currently present in the active schema."""
    inspector = inspect(engine)
    return set(inspector.get_table_names(schema=active_schema_name(engine)))


def create_tables(engine) -> None:
    """Create all application tables and indexes if they do not already exist.

    Also runs incremental column-migration helpers for tables that evolve over time.
    """
    with engine.begin() as conn:
        _ensure_schema(conn)
        for table_name, ddl in TABLE_DEFINITIONS.items():
            conn.execute(text(_qualify_ddl(engine, table_name, ddl)))
        for ddl in INDEX_DEFINITIONS.values():
            conn.execute(text(_qualify_index_ddl(engine, ddl)))
        ensure_security_metadata_schema(conn)
        ensure_macro_data_schema(conn)
        ensure_analytics_snapshot_schema(conn)


def ensure_security_metadata_schema(conn) -> None:
    """Add any columns missing from security_metadata introduced after the initial schema."""
    _add_missing_columns(conn, "security_metadata", {"duration": "REAL"})


def ensure_analytics_snapshot_schema(conn) -> None:
    """Add any columns missing from analytics_snapshots introduced after the initial schema."""
    _add_missing_columns(
        conn,
        "analytics_snapshots",
        {
            "model_version": "TEXT",
            "computed_from_start_date": "DATE",
            "computed_from_end_date": "DATE",
            "spread_beta_per_bp": "REAL",
            "benchmark_beta": "REAL",
        },
    )


def ensure_macro_data_schema(conn) -> None:
    """Migrate macro_data to the current column layout if the legacy schema is detected.

    This is a one-time destructive migration for SQLite only: it renames the old table,
    recreates it with the full column set, copies the overlapping rows, then drops the backup.
    """
    engine = conn.engine
    inspector = inspect(conn)
    schema = active_schema_name(engine)

    if "macro_data" not in set(inspector.get_table_names(schema=schema)):
        return

    existing_columns = [row["name"] for row in inspector.get_columns("macro_data", schema=schema)]
    if existing_columns == EXPECTED_MACRO_DATA_COLUMNS:
        return

    # Column migration is only safe on SQLite; Postgres supports ALTER TABLE ADD COLUMN.
    if engine.dialect.name != "sqlite":
        return

    conn.exec_driver_sql("ALTER TABLE macro_data RENAME TO macro_data_legacy")
    conn.execute(text(_qualify_ddl(engine, "macro_data", TABLE_DEFINITIONS["macro_data"])))

    legacy = set(existing_columns)
    source_expr = "COALESCE(source, 'fred')" if "source" in legacy else "'fred'"
    ts_expr = "updated_at" if "updated_at" in legacy else "CURRENT_TIMESTAMP"

    if {"series_id", "date", "value"}.issubset(legacy):
        conn.exec_driver_sql(f"""
            INSERT INTO macro_data (
                series_id, date, value, series_name, category, sub_category,
                frequency, units, source, is_active, last_updated_at
            )
            SELECT
                series_id, date, value,
                NULL, NULL, NULL, NULL, NULL,
                {source_expr}, 1, {ts_expr}
            FROM macro_data_legacy
        """)

    conn.exec_driver_sql("DROP TABLE macro_data_legacy")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _add_missing_columns(conn, table_name: str, missing_columns: dict[str, str]) -> None:
    """ALTER TABLE to add any columns from missing_columns that are not yet present."""
    engine = conn.engine
    inspector = inspect(conn)
    schema = active_schema_name(engine)

    if table_name not in set(inspector.get_table_names(schema=schema)):
        return

    existing = {row["name"] for row in inspector.get_columns(table_name, schema=schema)}
    for column_name, column_type in missing_columns.items():
        if column_name not in existing:
            conn.execute(text(
                f"ALTER TABLE {qualified_table(engine, table_name)} "
                f"ADD COLUMN {column_name} {column_type}"
            ))


def _ensure_schema(conn) -> None:
    """Create the Postgres schema if it does not exist (no-op for SQLite)."""
    if conn.engine.dialect.name != "postgresql":
        return
    schema = active_schema_name(conn.engine) or "public"
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def _qualify_ddl(engine, table_name: str, ddl: str) -> str:
    """Prefix the table name with its schema in a CREATE TABLE statement for Postgres."""
    if engine.dialect.name != "postgresql":
        return ddl
    return ddl.replace(
        f"CREATE TABLE IF NOT EXISTS {table_name}",
        f"CREATE TABLE IF NOT EXISTS {qualified_table(engine, table_name)}",
    )


def _qualify_index_ddl(engine, ddl: str) -> str:
    """Prefix all table references in a CREATE INDEX statement with the active schema."""
    if engine.dialect.name != "postgresql":
        return ddl
    result = ddl
    for table_name in TABLE_DEFINITIONS:
        result = result.replace(f" ON {table_name} ", f" ON {qualified_table(engine, table_name)} ")
    return result
