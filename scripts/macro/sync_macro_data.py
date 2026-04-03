import argparse

from config import FRED_API_KEY, FRED_BASE_URL
from db.connection import get_engine
from repositories.macro import MacroRepository
from services.macro import DEFAULT_MACRO_SERIES, FredClient, MacroDataService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load FRED macro time series into the local database.")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
        help="Choose whether to fully replace selected series or only catch up missing dates.",
    )
    parser.add_argument(
        "--series",
        help="Comma-separated list of FRED series IDs to process. If omitted, the default macro coverage set is used.",
    )
    parser.add_argument(
        "--start",
        help="Optional start date in YYYY-MM-DD format. For full mode, defaults to 2000-01-01.",
    )
    parser.add_argument(
        "--end",
        help="Optional end date in YYYY-MM-DD format. Defaults to today when omitted.",
    )
    parser.add_argument(
        "--overlap-days",
        type=int,
        default=7,
        help="For incremental mode, refetch this many days before the latest stored date.",
    )
    return parser


def parse_series_ids(series_arg: str | None) -> list[str]:
    if not series_arg:
        return list(DEFAULT_MACRO_SERIES.keys())

    series_ids = []
    for raw_value in series_arg.split(","):
        series_id = raw_value.strip().upper()
        if series_id and series_id not in series_ids:
            series_ids.append(series_id)
    return series_ids


if __name__ == "__main__":
    args = build_parser().parse_args()
    series_ids = parse_series_ids(args.series)

    engine = get_engine()
    repository = MacroRepository(engine)
    client = FredClient(api_key=FRED_API_KEY, base_url=FRED_BASE_URL)
    service = MacroDataService(client, repository)

    if args.mode == "full":
        start = args.start or "2000-01-01"
        service.sync_series_history(
            series_ids,
            start=start,
            end=args.end,
            replace_existing=True,
        )
        print(f"Replaced macro history for {len(series_ids)} series: {', '.join(series_ids)}")
    else:
        statuses = service.sync_incremental_updates(
            series_ids,
            overlap_days=args.overlap_days,
            default_start=args.start or "2000-01-01",
            end=args.end,
        )
        print("Incremental macro update complete:")
        for series_id in series_ids:
            print(f" - {series_id}: {statuses.get(series_id, 'not_processed')}")
