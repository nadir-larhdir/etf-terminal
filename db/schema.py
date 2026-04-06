from sqlalchemy import inspect, text

from db.sql import qualified_table, schema_name as active_schema_name


# SQLite table definitions managed by the database bootstrap script.
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
}

EXPECTED_MACRO_DATA_COLUMNS = [
    "series_id",
    "date",
    "value",
    "series_name",
    "category",
    "sub_category",
    "frequency",
    "units",
    "source",
    "is_active",
    "last_updated_at",
]

INDEX_DEFINITIONS = {
    "idx_price_history_date": "CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history (date)",
    "idx_price_history_ticker_date": "CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date ON price_history (ticker, date)",
    "idx_macro_data_date": "CREATE INDEX IF NOT EXISTS idx_macro_data_date ON macro_data (date)",
    "idx_macro_data_series_date": "CREATE INDEX IF NOT EXISTS idx_macro_data_series_date ON macro_data (series_id, date)",
    "idx_macro_features_date": "CREATE INDEX IF NOT EXISTS idx_macro_features_date ON macro_features (date)",
    "idx_macro_features_feature_date": "CREATE INDEX IF NOT EXISTS idx_macro_features_feature_date ON macro_features (feature_name, date)",
    "idx_securities_active_ticker": "CREATE INDEX IF NOT EXISTS idx_securities_active_ticker ON securities (active, ticker)",
}


def get_existing_tables(engine) -> set[str]:
    inspector = inspect(engine)
    return set(inspector.get_table_names(schema=active_schema_name(engine)))


def create_tables(engine):
    with engine.begin() as conn:
        _ensure_schema(conn)
        for table_name, ddl in TABLE_DEFINITIONS.items():
            conn.execute(text(_qualify_ddl(engine, table_name, ddl)))
        for ddl in INDEX_DEFINITIONS.values():
            conn.execute(text(_qualify_index_ddl(engine, ddl)))
        ensure_macro_data_schema(conn)


def ensure_macro_data_schema(conn):
    engine = conn.engine
    inspector = inspect(conn)
    schema_name = active_schema_name(engine)
    table_names = set(inspector.get_table_names(schema=schema_name))
    if "macro_data" not in table_names:
        return

    rows = inspector.get_columns("macro_data", schema=schema_name)
    if not rows:
        return

    existing_columns = [row["name"] for row in rows]
    if existing_columns == EXPECTED_MACRO_DATA_COLUMNS:
        return

    if engine.dialect.name != "sqlite":
        return

    conn.exec_driver_sql("ALTER TABLE macro_data RENAME TO macro_data_legacy")
    conn.execute(text(_qualify_ddl(engine, "macro_data", TABLE_DEFINITIONS["macro_data"])))
    legacy_columns = set(existing_columns)

    if {"series_id", "date", "value"}.issubset(legacy_columns):
        source_expression = "COALESCE(source, 'fred')" if "source" in legacy_columns else "'fred'"
        timestamp_expression = "updated_at" if "updated_at" in legacy_columns else "CURRENT_TIMESTAMP"
        insert_statement = """
        INSERT INTO macro_data (
            series_id,
            date,
            value,
            series_name,
            category,
            sub_category,
            frequency,
            units,
            source,
            is_active,
            last_updated_at
        )
        SELECT
            series_id,
            date,
            value,
            NULL AS series_name,
            NULL AS category,
            NULL AS sub_category,
            NULL AS frequency,
            NULL AS units,
            {source_expression} AS source,
            1 AS is_active,
            {timestamp_expression} AS last_updated_at
        FROM macro_data_legacy
        """.format(
            source_expression=source_expression,
            timestamp_expression=timestamp_expression,
        )
        conn.exec_driver_sql(insert_statement)

    conn.exec_driver_sql("DROP TABLE macro_data_legacy")


def _ensure_schema(conn) -> None:
    if conn.engine.dialect.name != "postgresql":
        return

    schema_name = active_schema_name(conn.engine) or "public"
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))


def _qualify_ddl(engine, table_name: str, ddl: str) -> str:
    if engine.dialect.name != "postgresql":
        return ddl
    return ddl.replace(
        f"CREATE TABLE IF NOT EXISTS {table_name}",
        f"CREATE TABLE IF NOT EXISTS {qualified_table(engine, table_name)}",
    )


def _qualify_index_ddl(engine, ddl: str) -> str:
    if engine.dialect.name != "postgresql":
        return ddl
    qualified = ddl
    for table_name in TABLE_DEFINITIONS:
        qualified = qualified.replace(f" ON {table_name} ", f" ON {qualified_table(engine, table_name)} ")
    return qualified
