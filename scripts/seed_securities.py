from config import DEFAULT_TICKERS
from db.connection import get_engine
from repositories.security_repository import SecurityRepository


if __name__ == "__main__":
    engine = get_engine()
    repo = SecurityRepository(engine)
    rows = [
        {"ticker": ticker, "name": meta["name"], "asset_class": meta["asset_class"], "active": 1}
        for ticker, meta in DEFAULT_TICKERS.items()
    ]
    repo.seed_securities(rows)
    print("Securities seeded.")
