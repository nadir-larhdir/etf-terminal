import logging
import argparse

from db.connection import get_engine
from fixed_income.analytics import DurationModelSelector, FixedIncomeAnalyticsService, is_snapshot_stale, snapshot_age_hours
from fixed_income.analytics.result_models import SecurityAnalyticsSnapshot
from fixed_income.instruments.security import Security
from scripts.logging_utils import configure_logging
from stores.analytics import AnalyticsSnapshotStore
from stores.macro import MacroStore
from stores.market import MetadataStore, PriceStore, SecurityStore


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Precompute fixed-income analytics snapshots.")
    parser.add_argument("--force", action="store_true", help="Recompute all symbols even when a fresh snapshot exists.")
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=24,
        help="Snapshot freshness threshold used to skip recomputation.",
    )
    return parser


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    engine = get_engine()
    security_store = SecurityStore(engine)
    price_store = PriceStore(engine)
    metadata_store = MetadataStore(engine)
    macro_store = MacroStore(engine)
    snapshot_store = AnalyticsSnapshotStore(engine)
    selector = DurationModelSelector()
    analytics_service = FixedIncomeAnalyticsService(price_store, macro_store, selector, snapshot_store)

    securities = security_store.list_active_securities()
    if securities.empty:
        logger.info("No active securities found for analytics precompute.")
        return

    tickers = securities["ticker"].astype(str).tolist()
    latest_price_dates = price_store.get_latest_stored_dates(tickers)
    latest_snapshot_rows = snapshot_store.get_latest_snapshots(securities["ticker"].astype(str).tolist())
    latest_snapshot_map = {
        str(row["symbol"]): row.to_dict() for _, row in latest_snapshot_rows.iterrows()
    } if not latest_snapshot_rows.empty else {}

    persisted = 0
    skipped = 0
    for _, row in securities.iterrows():
        ticker = str(row["ticker"])
        latest_price_date = latest_price_dates.get(ticker)
        snapshot = None
        if ticker in latest_snapshot_map:
            snapshot = SecurityAnalyticsSnapshot.from_record(latest_snapshot_map[ticker])
        if not args.force and not is_snapshot_stale(snapshot, ttl_hours=args.ttl_hours, required_as_of_date=latest_price_date):
            logger.info(
                "Skipping %s: fresh snapshot hit (age_hours=%.2f).",
                ticker,
                snapshot_age_hours(snapshot) or 0.0,
            )
            skipped += 1
            continue

        logger.info("Precomputing analytics for %s...", ticker)
        history = price_store.get_ticker_price_history(ticker)
        if history.empty:
            logger.warning("Skipping %s: no price history.", ticker)
            continue
        metadata = metadata_store.get_ticker_metadata(ticker) or {}
        security = Security(
            ticker=ticker,
            name=row.get("name"),
            asset_class=row.get("asset_class"),
            metadata=metadata,
            history=history,
        )
        snapshot = analytics_service.analyze_security(security)
        if snapshot.as_of_date is None:
            logger.warning("Skipping %s: no analytics as-of date.", ticker)
            continue
        analytics_service.persist_snapshot(snapshot, as_of_date=snapshot.as_of_date)
        persisted += 1

    logger.info("Analytics precompute complete: %s persisted, %s skipped.", persisted, skipped)


if __name__ == "__main__":
    main()
