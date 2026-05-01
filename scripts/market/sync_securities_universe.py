"""Seed or update the ETF universe in the database from the configured DEFAULT_TICKERS."""

import argparse
import logging

from config import DEFAULT_TICKERS
from db.connection import get_engine
from scripts.logging_utils import configure_logging
from scripts.script_helpers import add_ticker_argument, filter_new_ticker_rows, parse_ticker_list
from stores.market import ETFUniverseStore

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the sync_securities_universe script."""
    parser = argparse.ArgumentParser(description="Seed the ETF universe into the local database.")
    parser.add_argument(
        "--backend", choices=["local", "supabase"], default=None, help="Target data backend."
    )
    parser.add_argument(
        "--app-env",
        choices=["prod", "uat"],
        default=None,
        help="Local DB environment when using --backend local.",
    )
    parser.add_argument(
        "--mode",
        choices=["full-replace", "upsert", "missing-only"],
        default="upsert",
        help="Replace the full etf_universe table, upsert configured rows, or only add new tickers.",
    )
    add_ticker_argument(parser)
    return parser


if __name__ == "__main__":
    configure_logging()
    args = build_parser().parse_args()
    tickers = parse_ticker_list(args.tickers)

    engine = get_engine(data_backend=args.backend, app_env=args.app_env)
    etf_universe_store = ETFUniverseStore(engine)
    rows = [
        {"ticker": ticker, "name": meta["name"], "asset_class": meta["asset_class"], "active": 1}
        for ticker, meta in DEFAULT_TICKERS.items()
        if ticker in tickers
    ]

    if args.mode == "full-replace":
        etf_universe_store.replace_etf_universe(rows)
        logger.info("Replaced ETF universe with %s ticker(s): %s", len(rows), ", ".join(tickers))
    elif args.mode == "missing-only":
        existing = etf_universe_store.get_existing_tickers()
        new_rows = filter_new_ticker_rows(rows, existing)
        etf_universe_store.upsert_etfs(new_rows, update_existing=False)
        logger.info(
            "Inserted %s new ETF universe row(s): %s",
            len(new_rows),
            ", ".join(row["ticker"] for row in new_rows) if new_rows else "none",
        )
    else:
        etf_universe_store.upsert_etfs(rows, update_existing=True)
        logger.info("Upserted %s ETF universe row(s): %s", len(rows), ", ".join(tickers))
