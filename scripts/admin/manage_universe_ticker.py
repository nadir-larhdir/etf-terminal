import argparse

from db.connection import get_engine
from stores.market import InputStore, MetadataStore, PriceStore, SecurityStore
from services.admin import TickerManagerService
from services.market import MarketDataService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add or remove a ticker across the local ETF database.")
    parser.add_argument("action", choices=["add", "delete"], help="Whether to add or delete the ticker.")
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
        print("Ticker added successfully:")
        print(" - ticker: {0}".format(profile.ticker))
        print(" - name: {0}".format(profile.name))
        print(" - asset_class: {0}".format(profile.asset_class))
        print(" - quote_type: {0}".format(profile.diagnostics.get("quote_type") or "N/A"))
        print(" - category: {0}".format(profile.diagnostics.get("category") or "N/A"))
    else:
        manager.delete_ticker(args.ticker)
        print("Ticker deleted from securities, metadata, prices, and inputs: {0}".format(args.ticker.strip().upper()))
