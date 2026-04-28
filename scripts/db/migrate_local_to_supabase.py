"""Copy all tables from a local SQLite database into the configured Supabase schema."""

import argparse
import logging

from config import DB_SCHEMA
from db.connection import get_engine
from scripts.db.migration_utils import TABLE_COPY_ORDER, copy_table, parse_local_env, prepare_target
from scripts.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def migrate_environment(app_env: str) -> dict[str, int]:
    """Truncate the Supabase target, then copy all tables from the local env; return row counts."""
    source_engine = get_engine(data_backend="local", app_env=app_env)
    target_engine = get_engine(data_backend="supabase")

    prepare_target(target_engine)

    counts: dict[str, int] = {}
    for table_name in TABLE_COPY_ORDER:
        counts[table_name] = copy_table(
            source_engine, target_engine, table_name, normalize_for_target=True
        )
    return counts


def main() -> None:
    """Entry point: parse args, run the migration, and log per-table row counts."""
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

    source_env = parse_local_env(args.source_env, label="source")
    counts = migrate_environment(source_env)
    logger.info("Migrated local %s -> supabase schema %s", source_env, DB_SCHEMA)
    for table_name, row_count in counts.items():
        logger.info(" - %s: %s rows", table_name, row_count)


if __name__ == "__main__":
    main()
