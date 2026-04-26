import argparse
import logging
from datetime import datetime

from db.connection import get_engine
from scripts.logging_utils import configure_logging
from scripts.script_helpers import add_ticker_argument, filter_new_ticker_rows, parse_ticker_list
from stores.market import MetadataStore

# Static metadata rows used when you want a controlled in-house metadata baseline.
DEFAULT_METADATA = [
    {
        "ticker": "LQD",
        "conid": None,
        "long_name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "description": "Tracks a broad basket of USD-denominated investment grade corporate bonds and is commonly used as a liquid proxy for long-duration IG credit risk.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "Markit iBoxx USD Liquid Investment Grade Index",
        "category": "IG Credit",
        "duration_bucket": "Intermediate / Long Duration",
        "currency": "USD",
        "exchange": "NASDAQ",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "HYG",
        "conid": None,
        "long_name": "iShares iBoxx $ High Yield Corporate Bond ETF",
        "description": "Tracks USD-denominated high yield corporate bonds and is widely used as a liquid proxy for broad HY beta and risk sentiment.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "Markit iBoxx USD Liquid High Yield Index",
        "category": "HY Credit",
        "duration_bucket": "Intermediate Duration",
        "currency": "USD",
        "exchange": "NYSE Arca",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "IEF",
        "conid": None,
        "long_name": "iShares 7-10 Year Treasury Bond ETF",
        "description": "Tracks U.S. Treasury securities in the 7 to 10 year maturity bucket and is commonly used as a liquid belly-duration hedge.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "ICE U.S. Treasury 7-10 Year Bond Index",
        "category": "UST Belly",
        "duration_bucket": "7-10Y",
        "currency": "USD",
        "exchange": "NASDAQ",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "TLT",
        "conid": None,
        "long_name": "iShares 20+ Year Treasury Bond ETF",
        "description": "Tracks long-dated U.S. Treasury securities and is widely used as a liquid proxy for long duration and macro rate exposure.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "ICE U.S. Treasury 20+ Year Bond Index",
        "category": "UST Long",
        "duration_bucket": "20Y+",
        "currency": "USD",
        "exchange": "NASDAQ",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
    {
        "ticker": "AGG",
        "conid": None,
        "long_name": "iShares Core U.S. Aggregate Bond ETF",
        "description": "Tracks the broad U.S. investment grade bond market across Treasuries, agencies, MBS, and corporates and is often used as a core bond benchmark.",
        "issuer": "BlackRock / iShares",
        "benchmark_index": "Bloomberg U.S. Aggregate Bond Index",
        "category": "Core Bond",
        "duration_bucket": "Intermediate Duration",
        "currency": "USD",
        "exchange": "NYSE Arca",
        "source": "internal_seed",
        "updated_at": datetime.utcnow().isoformat(),
    },
]

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Seed static ETF metadata into the local database."
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
        "--mode",
        choices=["upsert", "missing-only"],
        default="upsert",
        help="Update metadata for selected tickers or only add rows that do not exist yet.",
    )
    add_ticker_argument(parser)
    args = parser.parse_args()

    selected_tickers = set(parse_ticker_list(args.tickers))
    engine = get_engine(data_backend=args.backend, app_env=args.app_env)
    metadata_store = MetadataStore(engine)
    rows = [row for row in DEFAULT_METADATA if row["ticker"] in selected_tickers]

    if args.mode == "missing-only":
        rows = filter_new_ticker_rows(rows, metadata_store.get_existing_tickers())

    metadata_store.upsert_metadata(rows)
    processed = ", ".join(row["ticker"] for row in rows) if rows else "none"
    logger.info("Static metadata processed for %s ticker(s): %s", len(rows), processed)
