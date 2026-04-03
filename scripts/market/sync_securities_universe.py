import argparse

from config import DEFAULT_TICKERS
from db.connection import get_engine
from stores.market import SecurityStore
from scripts.script_helpers import add_ticker_argument, filter_new_ticker_rows, parse_ticker_list


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
        print(f"Replaced securities universe with {len(rows)} ticker(s): {', '.join(tickers)}")
    elif args.mode == "missing-only":
        existing = security_store.get_existing_tickers()
        new_rows = filter_new_ticker_rows(rows, existing)
        security_store.upsert_securities(new_rows, update_existing=False)
        print(f"Inserted {len(new_rows)} new security row(s): {', '.join(row['ticker'] for row in new_rows) if new_rows else 'none'}")
    else:
        security_store.upsert_securities(rows, update_existing=True)
        print(f"Upserted {len(rows)} security row(s): {', '.join(tickers)}")
