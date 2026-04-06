import argparse
import logging

import pandas as pd
from sqlalchemy import text

from config import DB_SCHEMA
from config.config import ENV_DB_FILENAMES
from db.connection import get_engine
from db.schema import TABLE_DEFINITIONS, create_tables
from db.sql import pandas_to_sql_kwargs, qualified_table
from scripts.logging_utils import configure_logging


TABLE_COPY_ORDER = list(TABLE_DEFINITIONS.keys())
logger = logging.getLogger(__name__)


def _parse_source_env(raw_value: str) -> str:
    selected = raw_value.strip().lower()
    if selected not in ENV_DB_FILENAMES:
        raise SystemExit("Invalid source environment. Use --source-env prod or --source-env uat.")
    return selected


def _truncate_target_tables(engine) -> None:
    with engine.begin() as conn:
        for table_name in reversed(TABLE_COPY_ORDER):
            conn.execute(text(f"DELETE FROM {qualified_table(engine, table_name)}"))


def _copy_table(source_engine, target_engine, table_name: str) -> int:
    with source_engine.connect() as source_conn:
        frame = pd.read_sql(text(f"SELECT * FROM {table_name}"), source_conn)

    if frame.empty:
        return 0

    with target_engine.begin() as target_conn:
        frame.to_sql(table_name, target_conn, if_exists="append", index=False, **pandas_to_sql_kwargs(target_engine))
    return len(frame)


def migrate_environment(app_env: str) -> dict[str, int]:
    source_engine = get_engine(data_backend="local", app_env=app_env)
    target_engine = get_engine(data_backend="supabase")

    create_tables(target_engine)
    _truncate_target_tables(target_engine)

    counts: dict[str, int] = {}
    for table_name in TABLE_COPY_ORDER:
        counts[table_name] = _copy_table(source_engine, target_engine, table_name)
    return counts


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Copy one local SQLite ETF Terminal database into the Supabase public schema.",
    )
    parser.add_argument(
        "--source-env",
        default="uat",
        help="Local source environment to migrate from (prod or uat).",
    )
    args = parser.parse_args()

    source_env = _parse_source_env(args.source_env)
    counts = migrate_environment(source_env)
    logger.info("Migrated local %s -> supabase schema %s", source_env, DB_SCHEMA)
    for table_name, row_count in counts.items():
        logger.info(" - %s: %s rows", table_name, row_count)


if __name__ == "__main__":
    main()
