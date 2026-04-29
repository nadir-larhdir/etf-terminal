"""Fetch and merge ETF metadata from Financial Modeling Prep into the local database."""

import argparse
import logging
from datetime import UTC, datetime

from config import DEFAULT_TICKERS, FMP_API_KEY, FMP_BASE_URL, normalize_asset_class
from db.connection import get_engine
from scripts.logging_utils import configure_logging
from scripts.script_helpers import add_ticker_argument, parse_ticker_list
from services.market.duration_estimator import SecurityDurationEstimator, issuer_from_long_name
from services.market.fmp_client import FMPClient
from stores.market import MetadataStore

# Internal overrides for known fixed-income ETF metadata fields.
INTERNAL_METADATA = {
    "BND": {
        "benchmark_index": "Bloomberg U.S. Aggregate Float Adjusted Index",
        "category": "Core Bond",
    },
    "BSV": {
        "benchmark_index": "Bloomberg U.S. 1-5 Year Government/Credit Float Adjusted Index",
    },
    "EDV": {
        "benchmark_index": "Bloomberg U.S. Treasury STRIPS 20-30 Year Equal Par Bond Index",
        "duration_bucket": "Treasury STRIPS",
        "category": "UST Long",
    },
    "EMB": {
        "benchmark_index": "JPMorgan EMBI Global Core Index",
    },
    "FLOT": {
        "benchmark_index": "Bloomberg U.S. Floating Rate Note < 5 Years Index",
    },
    "FLRN": {
        "benchmark_index": "Bloomberg U.S. Dollar Floating Rate Note < 5 Years Index",
        "category": "Floating Rate",
    },
    "GOVT": {
        "benchmark_index": "ICE U.S. Treasury Core Bond Index",
    },
    "HYD": {
        "benchmark_index": "Bloomberg Municipal High Yield Index",
        "category": "HY Credit",
    },
    "IEI": {
        "benchmark_index": "ICE U.S. Treasury 3-7 Year Bond Index",
    },
    "IGSB": {
        "benchmark_index": "ICE BofA 1-5 Year US Corporate Index",
    },
    "IUSB": {
        "benchmark_index": "Bloomberg U.S. Universal Float Adjusted Index",
        "category": "Core Bond",
    },
    "JNK": {
        "benchmark_index": "Bloomberg High Yield Very Liquid Index",
    },
    "LQD": {
        "benchmark_index": "Markit iBoxx USD Liquid Investment Grade Index",
        "duration_bucket": "Intermediate / Long Duration",
        "category": "IG Credit",
    },
    "MBB": {
        "benchmark_index": "Bloomberg U.S. MBS Float Adjusted Index",
    },
    "MUB": {
        "benchmark_index": "ICE AMT-Free US National Municipal Index",
    },
    "PCY": {
        "benchmark_index": "DB Emerging Market USD Liquid Balanced Index",
    },
    "SHY": {
        "benchmark_index": "ICE U.S. Treasury 1-3 Year Bond Index",
    },
    "SHYG": {
        "benchmark_index": "Markit iBoxx USD Liquid High Yield 0-5 Index",
    },
    "SLQD": {
        "benchmark_index": "Markit iBoxx USD Liquid Investment Grade 0-5 Index",
        "category": "IG Credit",
    },
    "SJNK": {
        "benchmark_index": "Bloomberg U.S. High Yield 350mn Cash Pay 0-5 Yr 2% Capped Index",
    },
    "SPSB": {
        "benchmark_index": "Bloomberg U.S. 1-3 Year Corporate Bond Index",
    },
    "STIP": {
        "benchmark_index": "Bloomberg U.S. 0-5 Year TIPS Index",
        "category": "Inflation-Linked",
    },
    "TIP": {
        "benchmark_index": "Bloomberg U.S. TIPS Index",
        "category": "Inflation-Linked",
    },
    "VCIT": {
        "benchmark_index": "Bloomberg U.S. 5-10 Year Corporate Bond Index",
    },
    "VCSH": {
        "benchmark_index": "Bloomberg U.S. 1-5 Year Corporate Bond Index",
    },
    "VGSH": {
        "benchmark_index": "Bloomberg U.S. Treasury 1-3 Year Bond Index",
    },
    "VMBS": {
        "benchmark_index": "Bloomberg U.S. MBS Float Adjusted Index",
    },
    "VTEB": {
        "benchmark_index": "S&P National AMT-Free Municipal Bond Index",
    },
    "VWOB": {
        "benchmark_index": "Bloomberg USD Emerging Markets Government RIC Capped Index",
    },
    "HYG": {
        "benchmark_index": "Markit iBoxx USD Liquid High Yield Index",
        "duration_bucket": "Intermediate Duration",
        "category": "HY Credit",
    },
    "IEF": {
        "benchmark_index": "ICE U.S. Treasury 7-10 Year Bond Index",
        "duration_bucket": "7-10Y",
        "category": "UST Belly",
    },
    "TLT": {
        "benchmark_index": "ICE U.S. Treasury 20+ Year Bond Index",
        "duration_bucket": "20Y+",
        "category": "UST Long",
    },
    "AGG": {
        "benchmark_index": "Bloomberg U.S. Aggregate Bond Index",
        "duration_bucket": "Intermediate Duration",
        "category": "Core Bond",
    },
}

FMP_CLIENT = FMPClient(api_key=FMP_API_KEY, base_url=FMP_BASE_URL)
logger = logging.getLogger(__name__)


def _is_populated(value) -> bool:
    """Return True when value is non-None and not a blank/sentinel string."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip().upper() in {"", "N/A", "NONE", "NULL"}:
        return False
    return True


def _choose_preferred(*values):
    """Return the first value that passes the _is_populated check."""
    for value in values:
        if _is_populated(value):
            return value
    return None


def _choose_longer_text(*values):
    """Return the longest non-empty string from the given values."""
    populated = [str(value).strip() for value in values if _is_populated(value)]
    if not populated:
        return None
    return max(populated, key=len)


def get_etf_description(ticker: str) -> dict:
    """Fetch and merge ETF profile and ETF-info fields from FMP into a single flat dict."""
    profile = FMP_CLIENT.get_security_profile(ticker)
    etf_info = FMP_CLIENT.get_etf_info(ticker)

    return {
        "ticker": ticker.upper(),
        "long_name": _choose_preferred(
            etf_info.get("name"),
            etf_info.get("companyName"),
            profile.get("companyName"),
            profile.get("name"),
        ),
        "description": _choose_preferred(etf_info.get("description"), profile.get("description")),
        "category": _choose_preferred(etf_info.get("category"), profile.get("category")),
        "benchmark_index": _choose_preferred(
            etf_info.get("benchmark"),
            etf_info.get("benchmarkIndex"),
            profile.get("benchmark"),
            profile.get("benchmarkIndex"),
        ),
        "issuer": _choose_preferred(
            etf_info.get("fundFamily"),
            etf_info.get("issuer"),
            profile.get("fundFamily"),
            profile.get("companyName"),
        ),
        "expense_ratio": _choose_preferred(
            etf_info.get("expenseRatio"), profile.get("expenseRatio")
        ),
        "total_assets": _choose_preferred(
            etf_info.get("assetsUnderManagement"),
            etf_info.get("aum"),
            etf_info.get("totalAssets"),
            profile.get("totalAssets"),
            profile.get("mktCap"),
        ),
        "currency": _choose_preferred(etf_info.get("currency"), profile.get("currency")),
        "exchange": _choose_preferred(
            etf_info.get("exchangeShortName"),
            etf_info.get("exchange"),
            profile.get("exchangeShortName"),
            profile.get("exchange"),
        ),
        "quote_type": _choose_preferred(
            etf_info.get("type"),
            etf_info.get("quoteType"),
            profile.get("type"),
            profile.get("quoteType"),
        ),
    }


_ASSET_CLASS_RULES: list[tuple[tuple[str, ...], str | dict]] = [
    (
        ("treasury",),
        {
            "1-3": "UST Short",
            "short": "UST Short",
            "3-7": "UST Belly",
            "7-10": "UST Belly",
            "intermediate": "UST Belly",
            "20+": "UST Long",
            "long": "UST Long",
            "extended duration": "UST Long",
            "_default": "UST Broad",
        },
    ),
    (("high yield",), "HY Credit"),
    (("investment grade", "corporate", "credit"), "IG Credit"),
    (("mortgage", "mbs"), "MBS"),
    (("municipal", "muni", "tax-exempt"), "Municipal"),
    (("emerging markets",), "EM Debt"),
    (("tips", "inflation"), "Inflation-Linked"),
    (("floating rate",), "Floating Rate"),
    (("aggregate", "core", "total bond"), "Core Bond"),
]


def derive_asset_class(search_values: list[str]) -> str:
    """Infer an asset class label from metadata text fields using keyword matching."""
    search_blob = " ".join(value for value in search_values if _is_populated(value)).lower()

    for keywords, label in _ASSET_CLASS_RULES:
        if any(kw in search_blob for kw in keywords):
            if isinstance(label, dict):
                for sub_kw, sub_label in label.items():
                    if sub_kw != "_default" and sub_kw in search_blob:
                        return sub_label
                return label["_default"]
            return label
    return "Fixed Income"


_DURATION_BUCKET_RULES: list[tuple[tuple[str, ...], str]] = [
    (("strips", "zero-coupon", "zero coupon"), "Treasury STRIPS"),
    (("0-5", "1-3", "ultra short", "short-term"), "Short Duration"),
    (("3-7", "7-10", "intermediate"), "Intermediate Duration"),
    (("20+", "long", "extended duration"), "Long Duration"),
    (("floating rate",), "Floating Rate"),
    (("mortgage", "mbs"), "Securitized"),
    (("tips", "inflation"), "Inflation-Linked"),
]


def derive_duration_bucket(search_values: list[str]) -> str:
    """Infer a duration bucket label from metadata text using keyword matching."""
    search_blob = " ".join(value for value in search_values if _is_populated(value)).lower()
    for keywords, label in _DURATION_BUCKET_RULES:
        if any(kw in search_blob for kw in keywords):
            return label
    return "Broad Market"


def build_metadata_row(
    ticker: str,
    existing_row: dict | None = None,
    *,
    duration_estimator: SecurityDurationEstimator | None = None,
) -> dict:
    """Build a complete metadata dict for a ticker by merging FMP, internal, and existing data.

    Priority order: internal overrides > existing DB row > FMP response > config defaults.
    """
    base = DEFAULT_TICKERS.get(ticker, {})
    internal = INTERNAL_METADATA.get(ticker, {})
    fmp_meta = get_etf_description(ticker)
    existing = existing_row or {}

    search_values = [
        str(fmp_meta.get("category") or ""),
        str(fmp_meta.get("benchmark_index") or ""),
        str(fmp_meta.get("long_name") or ""),
        str(fmp_meta.get("description") or ""),
        str(existing.get("category") or ""),
        str(existing.get("benchmark_index") or ""),
        str(existing.get("long_name") or ""),
        str(existing.get("description") or ""),
        str(base.get("asset_class") or ""),
        str(base.get("name") or ""),
    ]
    derived_category = normalize_asset_class(derive_asset_class(search_values))
    derived_duration = derive_duration_bucket(search_values)
    long_name = _choose_preferred(
        fmp_meta.get("long_name"), existing.get("long_name"), base.get("name"), ticker
    )
    issuer = _choose_preferred(
        issuer_from_long_name(long_name),
        existing.get("issuer"),
        fmp_meta.get("issuer"),
        "N/A",
    )
    duration = None
    if duration_estimator is not None:
        duration = duration_estimator.estimate_duration(ticker)

    return {
        "ticker": ticker,
        "conid": _choose_preferred(existing.get("conid"), None),
        "long_name": long_name,
        "description": _choose_longer_text(existing.get("description"), fmp_meta.get("description"))
        or f"Fixed income ETF in the {derived_category} bucket.",
        "issuer": issuer,
        "duration": _choose_preferred(duration, existing.get("duration")),
        "benchmark_index": _choose_preferred(
            internal.get("benchmark_index"),
            existing.get("benchmark_index"),
            fmp_meta.get("benchmark_index"),
            "N/A",
        ),
        "category": _choose_preferred(
            internal.get("category"),
            (
                normalize_asset_class(existing.get("category"))
                if _is_populated(existing.get("category"))
                else None
            ),
            derived_category,
            fmp_meta.get("category"),
            base.get("asset_class"),
        ),
        "duration_bucket": _choose_preferred(
            internal.get("duration_bucket"),
            existing.get("duration_bucket"),
            derived_duration,
            "N/A",
        ),
        "currency": _choose_preferred(fmp_meta.get("currency"), existing.get("currency"), "USD"),
        "exchange": _choose_preferred(fmp_meta.get("exchange"), existing.get("exchange"), "N/A"),
        "expense_ratio": _choose_preferred(
            fmp_meta.get("expense_ratio"), existing.get("expense_ratio")
        ),
        "total_assets": _choose_preferred(
            fmp_meta.get("total_assets"), existing.get("total_assets")
        ),
        "quote_type": _choose_preferred(fmp_meta.get("quote_type"), existing.get("quote_type")),
        "source": "fmp_enriched_merged",
        "updated_at": datetime.now(UTC).isoformat(),
    }


if __name__ == "__main__":
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Enrich ETF metadata from Financial Modeling Prep."
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
        help="Refresh selected metadata rows or only enrich tickers with no metadata yet.",
    )
    add_ticker_argument(parser)
    args = parser.parse_args()

    engine = get_engine(data_backend=args.backend, app_env=args.app_env)
    metadata_store = MetadataStore(engine)
    duration_estimator = SecurityDurationEstimator(engine)
    tickers = parse_ticker_list(args.tickers)

    if args.mode == "missing-only":
        existing = metadata_store.get_existing_tickers()
        tickers = [ticker for ticker in tickers if ticker not in existing]

    rows = []
    for ticker in tickers:
        try:
            existing_row = metadata_store.get_ticker_metadata(ticker)
            row = build_metadata_row(
                ticker,
                existing_row=existing_row,
                duration_estimator=duration_estimator,
            )
            rows.append(row)
            logger.info("Enriched metadata for %s", ticker)
        except Exception as exc:
            logger.warning("Failed metadata enrichment for %s: %s", ticker, exc)

    metadata_store.upsert_metadata(rows)
    logger.info("Security metadata enrichment complete.")
