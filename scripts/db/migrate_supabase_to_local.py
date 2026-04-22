import argparse
import logging

from db.connection import get_engine
from scripts.db.migration_utils import TABLE_COPY_ORDER, copy_table, parse_local_env, prepare_target
from scripts.logging_utils import configure_logging


logger = logging.getLogger(__name__)


def migrate_to_local(app_env: str) -> dict[str, int]:
    source_engine = get_engine(data_backend="supabase")
    target_engine = get_engine(data_backend="local", app_env=app_env)

    prepare_target(target_engine)

    counts: dict[str, int] = {}
    for table_name in TABLE_COPY_ORDER:
        counts[table_name] = copy_table(source_engine, target_engine, table_name)
    return counts


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Copy the current Supabase ETF Terminal schema into a local SQLite database.",
    )
    parser.add_argument(
        "--target-env",
        default="uat",
        help="Local target environment to migrate into (prod or uat).",
    )
    args = parser.parse_args()

    target_env = parse_local_env(args.target_env, label="target")
    counts = migrate_to_local(target_env)
    logger.info("Migrated supabase -> local %s", target_env)
    for table_name, row_count in counts.items():
        logger.info(" - %s: %s rows", table_name, row_count)


if __name__ == "__main__":
    main()
