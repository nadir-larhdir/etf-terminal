from db.connection import get_engine
from db.schema import create_tables


if __name__ == "__main__":
    engine = get_engine()
    create_tables(engine)
    print("Database initialized.")
