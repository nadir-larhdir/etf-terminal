import argparse

from datetime import datetime

from config import DEFAULT_TICKERS, FMP_API_KEY, FMP_BASE_URL, normalize_asset_class
from db.connection import get_engine
from stores.market import MetadataStore
from scripts.script_helpers import add_ticker_argument, parse_ticker_list
from services.market.fmp_client import FMPClient


"""Internal overrides for known fixed-income ETF metadata fields."""
INTERNAL_METADATA = {
    "LQD": {
        "benchmark_index": "Markit iBoxx USD Liquid Investment Grade Index",
        "duration_bucket": "Intermediate / Long Duration",
        "category": "IG Credit",
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


def _is_populated(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip().upper() in {"", "N/A", "NONE", "NULL"}:
        return False
    return True


def _choose_preferred(*values):
    for value in values:
        if _is_populated(value):
            return value
    return None


def _choose_longer_text(*values):
    populated = [str(value).strip() for value in values if _is_populated(value)]
    if not populated:
        return None
    return max(populated, key=len)


def get_etf_description(ticker: str) -> dict:
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
        "expense_ratio": _choose_preferred(etf_info.get("expenseRatio"), profile.get("expenseRatio")),
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


def derive_asset_class(search_values: list[str]) -> str:
    search_blob = " ".join(value for value in search_values if _is_populated(value)).lower()

    if "treasury" in search_blob:
        if "1-3" in search_blob or "short" in search_blob:
            return "UST Short"
        if "3-7" in search_blob or "7-10" in search_blob or "intermediate" in search_blob:
            return "UST Belly"
        if "20+" in search_blob or "long" in search_blob or "extended duration" in search_blob:
            return "UST Long"
        return "UST Broad"
    if "high yield" in search_blob:
        return "HY Credit"
    if "investment grade" in search_blob or "corporate" in search_blob or "credit" in search_blob:
        return "IG Credit"
    if "mortgage" in search_blob or "mbs" in search_blob:
        return "MBS"
    if "municipal" in search_blob or "muni" in search_blob or "tax-exempt" in search_blob:
        return "Municipal"
    if "emerging markets" in search_blob:
        return "EM Debt"
    if "tips" in search_blob or "inflation" in search_blob:
        return "Inflation-Linked"
    if "floating rate" in search_blob:
        return "Floating Rate"
    if "aggregate" in search_blob or "core" in search_blob or "total bond" in search_blob:
        return "Core Bond"
    return "Fixed Income"


def derive_duration_bucket(search_values: list[str]) -> str:
    search_blob = " ".join(value for value in search_values if _is_populated(value)).lower()

    if "0-5" in search_blob or "1-3" in search_blob or "ultra short" in search_blob or "short-term" in search_blob:
        return "Short Duration"
    if "3-7" in search_blob or "7-10" in search_blob or "intermediate" in search_blob:
        return "Intermediate Duration"
    if "20+" in search_blob or "long" in search_blob or "extended duration" in search_blob:
        return "Long Duration"
    if "floating rate" in search_blob:
        return "Floating Rate"
    if "mortgage" in search_blob or "mbs" in search_blob:
        return "Securitized"
    if "tips" in search_blob or "inflation" in search_blob:
        return "Inflation-Linked"
    return "Broad Market"


def build_metadata_row(ticker: str, existing_row: dict | None = None) -> dict:
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

    return {
        "ticker": ticker,
        "conid": _choose_preferred(existing.get("conid"), None),
        "long_name": _choose_preferred(fmp_meta.get("long_name"), existing.get("long_name"), base.get("name"), ticker),
        "description": _choose_longer_text(existing.get("description"), fmp_meta.get("description"))
        or f"Fixed income ETF in the {derived_category} bucket.",
        "issuer": _choose_preferred(fmp_meta.get("issuer"), existing.get("issuer"), "N/A"),
        "benchmark_index": _choose_preferred(
            internal.get("benchmark_index"),
            existing.get("benchmark_index"),
            fmp_meta.get("benchmark_index"),
            "N/A",
        ),
        "category": _choose_preferred(
            internal.get("category"),
            normalize_asset_class(existing.get("category")) if _is_populated(existing.get("category")) else None,
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
        "expense_ratio": _choose_preferred(fmp_meta.get("expense_ratio"), existing.get("expense_ratio")),
        "total_assets": _choose_preferred(fmp_meta.get("total_assets"), existing.get("total_assets")),
        "quote_type": _choose_preferred(fmp_meta.get("quote_type"), existing.get("quote_type")),
        "source": "fmp_enriched_merged",
        "updated_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich ETF metadata from Financial Modeling Prep.")
    parser.add_argument(
        "--mode",
        choices=["upsert", "missing-only"],
        default="upsert",
        help="Refresh selected metadata rows or only enrich tickers with no metadata yet.",
    )
    add_ticker_argument(parser)
    args = parser.parse_args()

    engine = get_engine()
    metadata_store = MetadataStore(engine)
    tickers = parse_ticker_list(args.tickers)

    if args.mode == "missing-only":
        existing = metadata_store.get_existing_tickers()
        tickers = [ticker for ticker in tickers if ticker not in existing]

    rows = []
    for ticker in tickers:
        try:
            existing_row = metadata_store.get_ticker_metadata(ticker)
            row = build_metadata_row(ticker, existing_row=existing_row)
            rows.append(row)
            print(f"Enriched metadata for {ticker}")
        except Exception as exc:
            print(f"Failed metadata enrichment for {ticker}: {exc}")

    metadata_store.upsert_metadata(rows)
    print("Security metadata enrichment complete.")
