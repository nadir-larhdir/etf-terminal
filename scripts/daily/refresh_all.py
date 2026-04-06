import argparse

from config import FMP_API_KEY, FMP_BASE_URL, FRED_API_KEY, FRED_BASE_URL
from db.connection import get_engine
from stores.macro import MacroFeatureStore, MacroStore
from stores.market import MetadataStore, PriceStore, SecurityStore
from scripts.market.enrich_metadata_from_fmp import build_metadata_row
from services.macro import DEFAULT_MACRO_SERIES, FredClient, MacroDataService, MacroFeatureService
from services.market import MarketDataService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the end-of-day ETF Terminal refresh workflow.")
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
    return parser


def _latest_price_date(price_store: PriceStore, tickers: list[str]) -> str:
    latest = price_store.get_latest_stored_dates(tickers)
    return max(latest.values()) if latest else "n/a"


def _latest_macro_date(macro_store: MacroStore, series_ids: list[str]) -> str:
    latest = macro_store.get_latest_stored_dates(series_ids)
    return max(latest.values()) if latest else "n/a"


def _latest_feature_date(feature_store: MacroFeatureStore, feature_name: str = "UST_10Y_LEVEL") -> str:
    latest = feature_store.get_latest_feature_values([feature_name])
    if latest.empty:
        return "n/a"
    return str(latest.iloc[0]["date"])


def _refresh_metadata(metadata_store: MetadataStore, tickers: list[str]) -> int:
    rows = []
    for ticker in tickers:
        existing = metadata_store.get_ticker_metadata(ticker)
        rows.append(build_metadata_row(ticker, existing_row=existing))
    metadata_store.upsert_metadata(rows)
    return len(rows)


def main() -> None:
    args = build_parser().parse_args()

    engine = get_engine()
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

    print("Step 1/4: refreshing ETF prices...")
    price_statuses = market_service.sync_incremental_updates(
        tickers,
        period_for_new=args.price_period,
        overlap_days=args.price_overlap_days,
    )
    print(f"Price refresh complete for {len(price_statuses)} ticker(s).")

    print("Step 2/4: refreshing FRED macro series...")
    macro_statuses = macro_data_service.sync_incremental_updates(
        series_ids,
        overlap_days=args.macro_overlap_days,
        default_start="2000-01-01",
    )
    print(f"Macro refresh complete for {len(macro_statuses)} series.")

    print("Step 3/4: rebuilding macro features...")
    feature_rows = macro_feature_service.persist_features()
    print(f"Macro feature rebuild complete with {len(feature_rows)} upserted row(s).")

    if args.skip_metadata:
        refreshed_metadata = 0
        print("Step 4/4: skipping ETF metadata refresh.")
    else:
        print("Step 4/4: refreshing ETF metadata...")
        refreshed_metadata = _refresh_metadata(metadata_store, tickers)
        print(f"Metadata refresh complete for {refreshed_metadata} ticker(s).")

    print("\nRefresh summary")
    print(f" - latest ETF price date: {_latest_price_date(price_store, tickers)}")
    print(f" - latest macro date: {_latest_macro_date(macro_store, series_ids)}")
    print(f" - latest feature date: {_latest_feature_date(macro_feature_store)}")
    print(f" - metadata rows refreshed: {refreshed_metadata}")


if __name__ == "__main__":
    main()
