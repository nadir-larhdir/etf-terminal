"""Precompute and persist fixed-income analytics snapshots for all active ETFs."""

import argparse
import logging

from db.connection import get_engine
from fixed_income.analytics import (
    FixedIncomeAnalyticsService,
    RiskProxySelector,
    is_snapshot_stale,
    snapshot_age_hours,
)
from fixed_income.analytics.result_models import ETFAnalyticsSnapshot
from fixed_income.etfs import ETF
from scripts.logging_utils import configure_logging
from stores.analytics import AnalyticsSnapshotStore
from stores.macro import MacroStore
from stores.market import ETFUniverseStore, MetadataStore, PriceStore

logger = logging.getLogger(__name__)


def _metadata_duration(metadata: dict) -> float | None:
    """Extract a numeric duration from a metadata dict, returning None for missing or N/A values."""
    raw_value = metadata.get("duration")
    if raw_value in (None, "", "N/A"):
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the precompute_analytics script."""
    parser = argparse.ArgumentParser(description="Precompute fixed-income analytics snapshots.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute all symbols even when a fresh snapshot exists.",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=24,
        help="Snapshot freshness threshold used to skip recomputation.",
    )
    return parser


def run_precompute_analytics(
    *, engine=None, force: bool = False, ttl_hours: int = 24
) -> tuple[int, int]:
    """Compute and persist analytics snapshots for all active ETFs.

    Returns (persisted_count, skipped_count). Skips etf_universe whose snapshots
    are still within the ttl_hours freshness window unless force=True.
    """
    if engine is None:
        engine = get_engine()
    etf_universe_store = ETFUniverseStore(engine)
    price_store = PriceStore(engine)
    metadata_store = MetadataStore(engine)
    macro_store = MacroStore(engine)
    snapshot_store = AnalyticsSnapshotStore(engine)
    selector = RiskProxySelector()
    analytics_service = FixedIncomeAnalyticsService(
        price_store, macro_store, selector, snapshot_store
    )

    etf_universe = etf_universe_store.list_active_etfs()
    if etf_universe.empty:
        logger.info("No active ETFs found for analytics precompute.")
        return 0, 0

    tickers = etf_universe["ticker"].astype(str).tolist()
    latest_price_dates = price_store.get_latest_stored_dates(tickers)
    latest_snapshot_rows = snapshot_store.get_latest_snapshots(
        etf_universe["ticker"].astype(str).tolist()
    )
    latest_snapshot_map = (
        {str(row["symbol"]): row.to_dict() for _, row in latest_snapshot_rows.iterrows()}
        if not latest_snapshot_rows.empty
        else {}
    )

    persisted = 0
    skipped = 0
    for _, row in etf_universe.iterrows():
        ticker = str(row["ticker"])
        latest_price_date = latest_price_dates.get(ticker)
        metadata = metadata_store.get_ticker_metadata(ticker) or {}
        metadata_duration = _metadata_duration(metadata)
        snapshot = None
        if ticker in latest_snapshot_map:
            snapshot = ETFAnalyticsSnapshot.from_record(latest_snapshot_map[ticker])
        if not force and not is_snapshot_stale(
            snapshot,
            ttl_hours=ttl_hours,
            required_as_of_date=latest_price_date,
            required_estimated_duration=metadata_duration,
        ):
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
        security = ETF(
            ticker=ticker,
            name=row.get("name"),
            asset_class=row.get("asset_class"),
            metadata=metadata,
            history=history,
        )
        snapshot = analytics_service.analyze_etf(security)
        if snapshot.as_of_date is None:
            logger.warning("Skipping %s: no analytics as-of date.", ticker)
            continue
        analytics_service.persist_snapshot(snapshot, as_of_date=snapshot.as_of_date)
        persisted += 1

    logger.info("Analytics precompute complete: %s persisted, %s skipped.", persisted, skipped)
    return persisted, skipped


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    run_precompute_analytics(force=args.force, ttl_hours=args.ttl_hours)


if __name__ == "__main__":
    main()
