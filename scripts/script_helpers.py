import argparse

from config import DEFAULT_TICKERS


def parse_ticker_list(tickers_arg: str | None) -> list[str]:
    if not tickers_arg:
        return list(DEFAULT_TICKERS.keys())

    requested = []
    for raw_value in tickers_arg.split(","):
        ticker = raw_value.strip().upper()
        if ticker and ticker not in requested:
            requested.append(ticker)
    return requested


def resolve_target_tickers(
    tickers_arg: str | None,
    available_tickers: list[str] | None = None,
) -> list[str]:
    if tickers_arg:
        return parse_ticker_list(tickers_arg)

    if available_tickers:
        resolved = []
        for ticker in available_tickers:
            normalized = str(ticker).strip().upper()
            if normalized and normalized not in resolved:
                resolved.append(normalized)
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
