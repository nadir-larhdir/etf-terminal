import argparse
import logging

from config import DEFAULT_TICKERS
from db.connection import get_engine
from scripts.logging_utils import configure_logging
from scripts.script_helpers import add_ticker_argument, filter_new_ticker_rows, parse_ticker_list
from stores.market import SecurityStore


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed the securities universe into the local database.")
    parser.add_argument(
        "--mode",
        choices=["full-replace", "upsert", "missing-only"],
        default="upsert",
        help="Replace the full securities table, upsert configured rows, or only add new tickers.",
    )
    add_ticker_argument(parser)
    return parser


if __name__ == "__main__":
    configure_logging()
    args = build_parser().parse_args()
    tickers = parse_ticker_list(args.tickers)

    engine = get_engine()
    security_store = SecurityStore(engine)
    rows = [
        {"ticker": ticker, "name": meta["name"], "asset_class": meta["asset_class"], "active": 1}
        for ticker, meta in DEFAULT_TICKERS.items()
        if ticker in tickers
    ]

    if args.mode == "full-replace":
        security_store.replace_securities_universe(rows)
        logger.info("Replaced securities universe with %s ticker(s): %s", len(rows), ", ".join(tickers))
    elif args.mode == "missing-only":
        existing = security_store.get_existing_tickers()
        new_rows = filter_new_ticker_rows(rows, existing)
        security_store.upsert_securities(new_rows, update_existing=False)
        logger.info(
            "Inserted %s new security row(s): %s",
            len(new_rows),
            ", ".join(row["ticker"] for row in new_rows) if new_rows else "none",
        )
    else:
        security_store.upsert_securities(rows, update_existing=True)
        logger.info("Upserted %s security row(s): %s", len(rows), ", ".join(tickers))
