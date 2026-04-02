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
}


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
