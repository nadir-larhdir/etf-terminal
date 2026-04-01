

from datetime import datetime

import yfinance as yf

from config import DEFAULT_TICKERS
from db.connection import get_engine
from repositories.metadata_repository import MetadataRepository


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


def get_etf_description(ticker: str) -> dict:
    etf = yf.Ticker(ticker)
    info = etf.info or {}

    return {
        "ticker": ticker.upper(),
        "long_name": info.get("longName"),
        "description": info.get("longBusinessSummary"),
        "category": info.get("category"),
        "benchmark_index": info.get("benchmarkName"),
        "issuer": info.get("fundFamily"),
        "expense_ratio": info.get("annualReportExpenseRatio"),
        "total_assets": info.get("totalAssets"),
        "currency": info.get("currency"),
        "exchange": info.get("exchange"),
        "quote_type": info.get("quoteType"),
    }



def build_metadata_row(ticker: str) -> dict:
    base = DEFAULT_TICKERS.get(ticker, {})
    internal = INTERNAL_METADATA.get(ticker, {})
    yf_meta = get_etf_description(ticker)

    return {
        "ticker": ticker,
        "conid": None,
        "long_name": yf_meta.get("long_name") or base.get("name"),
        "description": yf_meta.get("description") or f"Fixed income ETF in the {base.get('asset_class', 'Unknown')} bucket.",
        "issuer": yf_meta.get("issuer") or "N/A",
        "benchmark_index": internal.get("benchmark_index") or yf_meta.get("benchmark_index") or "N/A",
        "category": internal.get("category") or yf_meta.get("category") or base.get("asset_class"),
        "duration_bucket": internal.get("duration_bucket") or "N/A",
        "currency": yf_meta.get("currency") or "USD",
        "exchange": yf_meta.get("exchange") or "N/A",
        "expense_ratio": yf_meta.get("expense_ratio"),
        "total_assets": yf_meta.get("total_assets"),
        "quote_type": yf_meta.get("quote_type"),
        "source": "yfinance_enriched",
        "updated_at": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    engine = get_engine()
    repo = MetadataRepository(engine)

    rows = []
    for ticker in DEFAULT_TICKERS.keys():
        try:
            row = build_metadata_row(ticker)
            rows.append(row)
            print(f"Enriched metadata for {ticker}")
        except Exception as exc:
            print(f"Failed metadata enrichment for {ticker}: {exc}")

    repo.upsert_metadata(rows)
    print("Security metadata enrichment complete.")