import argparse
import logging

from db.connection import get_engine
from scripts.logging_utils import configure_logging
from scripts.script_helpers import add_ticker_argument, resolve_target_tickers
from services.market import MarketDataService
from stores.market import PriceStore, SecurityStore

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load ETF price history into the local database.")
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
    configure_logging()
    args = build_parser().parse_args()

    engine = get_engine(data_backend=args.backend, app_env=args.app_env)
    security_store = SecurityStore(engine)
    active_securities = security_store.list_active_securities()
    db_tickers = (
        active_securities["ticker"].astype(str).tolist() if not active_securities.empty else []
    )
    tickers = resolve_target_tickers(args.tickers, available_tickers=db_tickers)

    price_store = PriceStore(engine)
    service = MarketDataService(price_store)

    if args.mode == "full":
        service.sync_price_history(tickers, period=args.period, replace_existing=True)
        logger.info("Replaced price history for %s ticker(s): %s", len(tickers), ", ".join(tickers))
    elif args.mode == "gap-fill":
        service.sync_price_gaps(tickers, period=args.period)
        logger.info(
            "Gap-filled price history for %s ticker(s): %s", len(tickers), ", ".join(tickers)
        )
    elif args.mode == "missing-only":
        loaded = service.sync_missing_ticker_history(tickers, period=args.period)
        skipped = [ticker for ticker in tickers if ticker not in loaded]
        logger.info(
            "Initialized new ticker history for %s ticker(s): %s",
            len(loaded),
            ", ".join(loaded) if loaded else "none",
        )
        if skipped:
            logger.info(
                "Skipped existing ticker history for %s ticker(s): %s",
                len(skipped),
                ", ".join(skipped),
            )
    else:
        statuses = service.sync_incremental_updates(
            tickers,
            period_for_new=args.period,
            overlap_days=args.overlap_days,
        )
        logger.info("Incremental price update complete:")
        for ticker in tickers:
            logger.info(" - %s: %s", ticker, statuses.get(ticker, "not_processed"))
