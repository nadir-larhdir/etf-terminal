import argparse

from config import DEFAULT_TICKERS


def dedupe_upper(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value).strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def parse_csv_values(values_arg: str | None) -> list[str]:
    if not values_arg:
        return []
    return dedupe_upper(values_arg.split(","))


def parse_ticker_list(tickers_arg: str | None) -> list[str]:
    if not tickers_arg:
        return list(DEFAULT_TICKERS.keys())
    return parse_csv_values(tickers_arg)


def resolve_target_tickers(
    tickers_arg: str | None,
    available_tickers: list[str] | None = None,
) -> list[str]:
    if tickers_arg:
        return parse_ticker_list(tickers_arg)

    if available_tickers:
        resolved = dedupe_upper(available_tickers)
        if resolved:
            return resolved

    return list(DEFAULT_TICKERS.keys())


def filter_new_ticker_rows(rows: list[dict], existing_tickers: set[str]) -> list[dict]:
    return [row for row in rows if row["ticker"] not in existing_tickers]


def add_ticker_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tickers",
        help="Comma-separated list of tickers to process. If omitted, scripts can use the active DB universe and otherwise fall back to configured tickers.",
    )
