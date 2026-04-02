import argparse

from db.connection import get_engine
from repositories.market import PriceRepository, SecurityRepository
from scripts.script_helpers import add_ticker_argument, resolve_target_tickers
from services.market import MarketDataService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load ETF price history into the local database.")
    parser.add_argument(
        "--mode",
        choices=["full", "gap-fill", "incremental", "missing-only"],
        default="incremental",
        help="Choose whether to replace history, fill gaps, catch up recent dates, or only initialize new tickers.",
    )
    parser.add_argument(
        "--period",
        default="1y",
        help="Lookback window to use for full, gap-fill, or missing-only loads and for new tickers in incremental mode.",
    )
    parser.add_argument(
        "--overlap-days",
        type=int,
        default=5,
        help="For incremental mode, refetch this many days before the latest stored date to safely cover revisions and holidays.",
    )
    add_ticker_argument(parser)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()

    engine = get_engine()
    security_repo = SecurityRepository(engine)
    active_securities = security_repo.list_active_securities()
    db_tickers = active_securities["ticker"].astype(str).tolist() if not active_securities.empty else []
    tickers = resolve_target_tickers(args.tickers, available_tickers=db_tickers)

    repo = PriceRepository(engine)
    service = MarketDataService(repo)

    if args.mode == "full":
        service.sync_price_history(tickers, period=args.period, replace_existing=True)
        print(f"Replaced price history for {len(tickers)} ticker(s): {', '.join(tickers)}")
    elif args.mode == "gap-fill":
        service.sync_price_gaps(tickers, period=args.period)
        print(f"Gap-filled price history for {len(tickers)} ticker(s): {', '.join(tickers)}")
    elif args.mode == "missing-only":
        loaded = service.sync_missing_ticker_history(tickers, period=args.period)
        skipped = [ticker for ticker in tickers if ticker not in loaded]
        print(f"Initialized new ticker history for {len(loaded)} ticker(s): {', '.join(loaded) if loaded else 'none'}")
        if skipped:
            print(f"Skipped existing ticker history for {len(skipped)} ticker(s): {', '.join(skipped)}")
    else:
        statuses = service.sync_incremental_updates(
            tickers,
            period_for_new=args.period,
            overlap_days=args.overlap_days,
        )
        print("Incremental price update complete:")
        for ticker in tickers:
            print(f" - {ticker}: {statuses.get(ticker, 'not_processed')}")
