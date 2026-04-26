import argparse
import logging

from db.connection import get_engine
from scripts.logging_utils import configure_logging
from services.admin import TickerManagerService
from services.market import MarketDataService
from stores.market import InputStore, MetadataStore, PriceStore, SecurityStore

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add or remove a ticker across the local ETF database."
    )
    parser.add_argument(
        "action", choices=["add", "delete"], help="Whether to add or delete the ticker."
    )
    parser.add_argument("ticker", help="Ticker symbol to manage.")
    parser.add_argument(
        "--asset-class",
        help="Optional asset class override used when adding a ticker.",
    )
    parser.add_argument(
        "--period",
        default="1y",
        help="Price history period to load when adding a ticker.",
    )
    return parser


if __name__ == "__main__":
    configure_logging()
    args = build_parser().parse_args()

    engine = get_engine()
    security_store = SecurityStore(engine)
    price_store = PriceStore(engine)
    metadata_store = MetadataStore(engine)
    input_store = InputStore(engine)
    market_data_service = MarketDataService(price_store)
    manager = TickerManagerService(
        security_store=security_store,
        price_store=price_store,
        metadata_store=metadata_store,
        input_store=input_store,
        market_data_service=market_data_service,
    )

    if args.action == "add":
        profile = manager.add_ticker(
            args.ticker,
            asset_class_override=args.asset_class,
            period=args.period,
        )
        logger.info("Ticker added successfully:")
        logger.info(" - ticker: %s", profile.ticker)
        logger.info(" - name: %s", profile.name)
        logger.info(" - asset_class: %s", profile.asset_class)
        logger.info(" - quote_type: %s", profile.diagnostics.get("quote_type") or "N/A")
        logger.info(" - category: %s", profile.diagnostics.get("category") or "N/A")
    else:
        manager.delete_ticker(args.ticker)
        logger.info(
            "Ticker deleted from securities, metadata, prices, and inputs: %s",
            args.ticker.strip().upper(),
        )
