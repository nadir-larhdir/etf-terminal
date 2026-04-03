from sqlalchemy import text


"""SQLite table definitions managed by the database bootstrap script."""
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


def get_existing_tables(engine) -> set[str]:
    query = text(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
    return {row[0] for row in rows}


def create_tables(engine):
    with engine.begin() as conn:
        for ddl in TABLE_DEFINITIONS.values():
            conn.execute(text(ddl))
        ensure_macro_data_schema(conn)


def ensure_macro_data_schema(conn):
    rows = conn.exec_driver_sql("PRAGMA table_info(macro_data)").fetchall()
    if not rows:
        return

    existing_columns = [row[1] for row in rows]
    if existing_columns == EXPECTED_MACRO_DATA_COLUMNS:
        return

    conn.exec_driver_sql("ALTER TABLE macro_data RENAME TO macro_data_legacy")
    conn.execute(text(TABLE_DEFINITIONS["macro_data"]))
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
