import argparse

from datetime import datetime

from config import DEFAULT_TICKERS, FMP_API_KEY, FMP_BASE_URL
from db.connection import get_engine
from repositories.market import MetadataRepository
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


def get_etf_description(ticker: str) -> dict:
    info = FMP_CLIENT.get_security_profile(ticker)

    return {
        "ticker": ticker.upper(),
        "long_name": info.get("companyName") or info.get("name"),
        "description": info.get("description"),
        "category": info.get("category"),
        "benchmark_index": info.get("benchmark") or info.get("benchmarkIndex"),
        "issuer": info.get("fundFamily") or info.get("companyName"),
        "expense_ratio": info.get("expenseRatio"),
        "total_assets": info.get("mktCap") or info.get("totalAssets"),
        "currency": info.get("currency"),
        "exchange": info.get("exchangeShortName") or info.get("exchange"),
        "quote_type": info.get("type") or info.get("quoteType"),
    }



def build_metadata_row(ticker: str) -> dict:
    base = DEFAULT_TICKERS.get(ticker, {})
    internal = INTERNAL_METADATA.get(ticker, {})
    fmp_meta = get_etf_description(ticker)

    return {
        "ticker": ticker,
        "conid": None,
        "long_name": fmp_meta.get("long_name") or base.get("name"),
        "description": fmp_meta.get("description") or f"Fixed income ETF in the {base.get('asset_class', 'Unknown')} bucket.",
        "issuer": fmp_meta.get("issuer") or "N/A",
        "benchmark_index": internal.get("benchmark_index") or fmp_meta.get("benchmark_index") or "N/A",
        "category": internal.get("category") or fmp_meta.get("category") or base.get("asset_class"),
        "duration_bucket": internal.get("duration_bucket") or "N/A",
        "currency": fmp_meta.get("currency") or "USD",
        "exchange": fmp_meta.get("exchange") or "N/A",
        "expense_ratio": fmp_meta.get("expense_ratio"),
        "total_assets": fmp_meta.get("total_assets"),
        "quote_type": fmp_meta.get("quote_type"),
        "source": "fmp_enriched",
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
    repo = MetadataRepository(engine)
    tickers = parse_ticker_list(args.tickers)

    if args.mode == "missing-only":
        existing = repo.get_existing_tickers()
        tickers = [ticker for ticker in tickers if ticker not in existing]

    rows = []
    for ticker in tickers:
        try:
            row = build_metadata_row(ticker)
            rows.append(row)
            print(f"Enriched metadata for {ticker}")
        except Exception as exc:
            print(f"Failed metadata enrichment for {ticker}: {exc}")

    repo.upsert_metadata(rows)
    print("Security metadata enrichment complete.")
