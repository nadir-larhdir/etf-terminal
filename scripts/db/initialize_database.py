import logging

from config import APP_ENV, DATA_BACKEND, DB_SCHEMA
from db.connection import get_engine
from db.schema import TABLE_DEFINITIONS, create_tables, get_existing_tables
from scripts.logging_utils import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    engine = get_engine()
    existing_before = get_existing_tables(engine)
    create_tables(engine)
    existing_after = get_existing_tables(engine)

    managed_tables = list(TABLE_DEFINITIONS.keys())
    created_tables = [
        table
        for table in managed_tables
        if table not in existing_before and table in existing_after
    ]
    already_present = [table for table in managed_tables if table in existing_before]

    logger.info("Database initialized.")
    logger.info("Environment: %s", APP_ENV)
    logger.info("Backend: %s", DATA_BACKEND)
    if DATA_BACKEND == "supabase":
        logger.info("Schema: %s", DB_SCHEMA)
    logger.info("Managed tables: %s", ", ".join(managed_tables))
    logger.info("Created tables: %s", ", ".join(created_tables) if created_tables else "none")
    logger.info("Already present: %s", ", ".join(already_present) if already_present else "none")


if __name__ == "__main__":
    main()
