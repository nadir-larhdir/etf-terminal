from config import DEFAULT_TICKERS
from db.connection import get_engine
from repositories.price_repository import PriceRepository
from services.market_data_service import MarketDataService


if __name__ == "__main__":
    engine = get_engine()
    repo = PriceRepository(engine)
    service = MarketDataService(repo)
    service.backfill(list(DEFAULT_TICKERS.keys()), period="1y")
    print("Prices backfilled.")
