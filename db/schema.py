from sqlalchemy import text


def create_tables(engine):
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS securities (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            asset_class TEXT,
            active INTEGER DEFAULT 1
        )
        """))

        conn.execute(text("""
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
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS security_inputs (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            flow_usd_mm REAL DEFAULT 0,
            premium_discount_pct REAL DEFAULT 0,
            desk_note TEXT DEFAULT '',
            updated_at TEXT,
            PRIMARY KEY (ticker, date)
        )
        """))
