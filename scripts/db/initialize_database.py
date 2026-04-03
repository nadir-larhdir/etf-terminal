from db.connection import get_engine
from db.schema import TABLE_DEFINITIONS, create_tables, get_existing_tables


def main() -> None:
    engine = get_engine()
    existing_before = get_existing_tables(engine)
    create_tables(engine)
    existing_after = get_existing_tables(engine)

    managed_tables = list(TABLE_DEFINITIONS.keys())
    created_tables = [table for table in managed_tables if table not in existing_before and table in existing_after]
    already_present = [table for table in managed_tables if table in existing_before]

    print("Database initialized.")
    print("Managed tables: {0}".format(", ".join(managed_tables)))
    print("Created tables: {0}".format(", ".join(created_tables) if created_tables else "none"))
    print("Already present: {0}".format(", ".join(already_present) if already_present else "none"))


if __name__ == "__main__":
    main()
