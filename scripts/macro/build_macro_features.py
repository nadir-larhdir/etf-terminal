"""Build derived macro features from raw FRED series stored in the database."""

import logging
import argparse

from db.connection import get_engine
from stores.macro import MacroFeatureStore, MacroStore
from scripts.logging_utils import configure_logging
from services.macro import MacroFeatureService

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the build_macro_features script."""
    parser = argparse.ArgumentParser(description="Build derived macro features.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Rebuild the full macro feature history instead of the incremental window.",
    )
    parser.add_argument(
        "--rebuild-days",
        type=int,
        default=MacroFeatureService.DEFAULT_INCREMENTAL_REBUILD_DAYS,
        help="How many recent calendar days to recompute in incremental mode.",
    )
    parser.add_argument(
        "--warmup-days",
        type=int,
        default=MacroFeatureService.DEFAULT_WARMUP_DAYS,
        help="How many extra calendar days of source history to load for rolling calculations.",
    )
    parser.add_argument(
        "--backend",
        choices=["local", "supabase"],
        help="Override the configured data backend for this run.",
    )
    parser.add_argument(
        "--app-env",
        choices=["uat", "prod"],
        help="Override the configured app environment for local runs.",
    )
    return parser


def main() -> None:
    """Entry point: run incremental or full macro feature build and log per-feature row counts."""
    configure_logging()
    args = build_parser().parse_args()
    engine = get_engine(data_backend=args.backend, app_env=args.app_env)
    macro_store = MacroStore(engine)
    feature_store = MacroFeatureStore(engine)
    service = MacroFeatureService(macro_store, feature_store)

    rows = service.persist_features(
        incremental=not args.full,
        rebuild_days=args.rebuild_days,
        warmup_days=args.warmup_days,
    )
    if rows.empty:
        logger.info("No macro features were generated.")
    else:
        counts = rows.groupby("feature_name").size().sort_index()
        logger.info("Macro feature build complete:")
        for feature_name, row_count in counts.items():
            logger.info(" - %s: %s", feature_name, row_count)


if __name__ == "__main__":
    main()
