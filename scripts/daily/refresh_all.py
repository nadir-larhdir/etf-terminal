"""End-of-day orchestration script: prices, macro, features, metadata, and analytics snapshots."""

import argparse
import logging

from config import DEFAULT_TICKERS, FRED_API_KEY, FRED_BASE_URL
from db.connection import get_engine
from scripts.analytics.precompute_analytics import run_precompute_analytics
from scripts.logging_utils import configure_logging
from scripts.market.enrich_metadata_from_fmp import build_metadata_row
from services.macro import DEFAULT_MACRO_SERIES, FredClient, MacroDataService, MacroFeatureService
from services.market import MarketDataService
from services.market.duration_estimator import SecurityDurationEstimator
from stores.macro import MacroFeatureStore, MacroStore
from stores.market import MetadataStore, PriceStore, SecurityStore

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the daily refresh orchestration script."""
    parser = argparse.ArgumentParser(
        description="Run the end-of-day ETF Terminal refresh workflow."
    )
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
        "--price-period",
        default="3y",
        help="Lookback used only for new tickers during incremental price updates.",
    )
    parser.add_argument(
        "--price-overlap-days",
        type=int,
        default=5,
        help="Overlap window for incremental ETF price refreshes.",
    )
    parser.add_argument(
        "--macro-overlap-days",
        type=int,
        default=7,
        help="Overlap window for incremental macro refreshes.",
    )
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Skip ETF metadata refresh from FMP.",
    )
    parser.add_argument(
        "--skip-analytics",
        action="store_true",
        help="Skip analytics snapshot refresh.",
    )
    parser.add_argument(
        "--feature-rebuild-days",
        type=int,
        default=MacroFeatureService.DEFAULT_INCREMENTAL_REBUILD_DAYS,
        help="How many recent calendar days of macro features to recompute.",
    )
    parser.add_argument(
        "--feature-warmup-days",
        type=int,
        default=MacroFeatureService.DEFAULT_WARMUP_DAYS,
        help="Extra raw history window used to support rolling feature calculations.",
    )
    parser.add_argument(
        "--analytics-ttl-hours",
        type=int,
        default=24,
        help="Snapshot freshness threshold used when analytics precompute runs.",
    )
    parser.add_argument(
        "--force-analytics",
        action="store_true",
        help="Force analytics recomputation for all symbols.",
    )
    return parser


def _latest_price_date(price_store: PriceStore, tickers: list[str]) -> str:
    """Return the most recent stored price date across the given tickers, or 'n/a'."""
    latest = price_store.get_latest_stored_dates(tickers)
    return max(latest.values()) if latest else "n/a"


def _latest_macro_date(macro_store: MacroStore, series_ids: list[str]) -> str:
    """Return the most recent stored macro observation date across the given series, or 'n/a'."""
    latest = macro_store.get_latest_stored_dates(series_ids)
    return max(latest.values()) if latest else "n/a"


def _latest_feature_date(
    feature_store: MacroFeatureStore, feature_name: str = "UST_10Y_LEVEL"
) -> str:
    """Return the most recent macro feature date for the sentinel feature, or 'n/a'."""
    latest = feature_store.get_latest_feature_values([feature_name])
    if latest.empty:
        return "n/a"
    return str(latest.iloc[0]["date"])


def _refresh_metadata(metadata_store: MetadataStore, tickers: list[str]) -> int:
    """Fetch and upsert FMP metadata for each ticker; return the row count."""
    duration_estimator = SecurityDurationEstimator(metadata_store.engine)
    rows = []
    for ticker in tickers:
        existing = metadata_store.get_ticker_metadata(ticker)
        rows.append(
            build_metadata_row(
                ticker,
                existing_row=existing,
                duration_estimator=duration_estimator,
            )
        )
    metadata_store.upsert_metadata(rows)
    return len(rows)


def _refresh_universe(security_store: SecurityStore) -> int:
    """Upsert the configured DEFAULT_TICKERS universe into the securities table; return row count."""
    rows = [
        {"ticker": ticker, "name": meta["name"], "asset_class": meta["asset_class"], "active": 1}
        for ticker, meta in DEFAULT_TICKERS.items()
    ]
    security_store.upsert_securities(rows, update_existing=True)
    return len(rows)


def main() -> None:
    """Entry point: orchestrate the 6-step end-of-day refresh and log a summary."""
    configure_logging()
    args = build_parser().parse_args()
    run_analytics = not args.skip_analytics

    engine = get_engine(data_backend=args.backend, app_env=args.app_env)
    security_store = SecurityStore(engine)
    price_store = PriceStore(engine)
    metadata_store = MetadataStore(engine)
    macro_store = MacroStore(engine)
    macro_feature_store = MacroFeatureStore(engine)

    active = security_store.list_active_securities()
    tickers = active["ticker"].astype(str).tolist() if not active.empty else []
    series_ids = list(DEFAULT_MACRO_SERIES.keys())

    market_service = MarketDataService(price_store)
    fred_client = FredClient(api_key=FRED_API_KEY, base_url=FRED_BASE_URL)
    macro_data_service = MacroDataService(fred_client, macro_store)
    macro_feature_service = MacroFeatureService(macro_store, macro_feature_store)

    total_steps = 6 if run_analytics else 5

    logger.info("Step 1/%s: syncing configured securities universe...", total_steps)
    universe_rows = _refresh_universe(security_store)
    active = security_store.list_active_securities()
    tickers = active["ticker"].astype(str).tolist() if not active.empty else []

    logger.info("Step 2/%s: refreshing ETF prices...", total_steps)
    price_statuses = market_service.sync_incremental_updates(
        tickers,
        period_for_new=args.price_period,
        overlap_days=args.price_overlap_days,
    )
    logger.info("Price refresh complete for %s ticker(s).", len(price_statuses))

    logger.info("Step 3/%s: refreshing FRED macro series...", total_steps)
    macro_statuses = macro_data_service.sync_incremental_updates(
        series_ids,
        overlap_days=args.macro_overlap_days,
        default_start="2000-01-01",
    )
    logger.info("Macro refresh complete for %s series.", len(macro_statuses))

    logger.info("Step 4/%s: rebuilding macro features...", total_steps)
    feature_rows = macro_feature_service.persist_features(
        incremental=True,
        rebuild_days=args.feature_rebuild_days,
        warmup_days=args.feature_warmup_days,
    )
    logger.info("Macro feature rebuild complete with %s upserted row(s).", len(feature_rows))

    if args.skip_metadata:
        refreshed_metadata = 0
        logger.info("Step 5/%s: skipping ETF metadata refresh.", total_steps)
    else:
        logger.info("Step 5/%s: refreshing ETF metadata...", total_steps)
        refreshed_metadata = _refresh_metadata(metadata_store, tickers)
        logger.info("Metadata refresh complete for %s ticker(s).", refreshed_metadata)

    analytics_persisted = 0
    analytics_skipped = 0
    if run_analytics:
        logger.info("Step 6/%s: precomputing analytics snapshots...", total_steps)
        analytics_persisted, analytics_skipped = run_precompute_analytics(
            engine=engine,
            force=args.force_analytics,
            ttl_hours=args.analytics_ttl_hours,
        )

    logger.info("Refresh summary")
    logger.info(" - securities universe rows synced: %s", universe_rows)
    logger.info(" - latest ETF price date: %s", _latest_price_date(price_store, tickers))
    logger.info(" - latest macro date: %s", _latest_macro_date(macro_store, series_ids))
    logger.info(" - latest feature date: %s", _latest_feature_date(macro_feature_store))
    logger.info(" - metadata rows refreshed: %s", refreshed_metadata)
    if run_analytics:
        logger.info(" - analytics snapshots persisted: %s", analytics_persisted)
        logger.info(" - analytics snapshots skipped: %s", analytics_skipped)


if __name__ == "__main__":
    main()
