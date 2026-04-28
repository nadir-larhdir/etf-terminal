"""Shared argument-parsing and ticker-resolution utilities for scripts."""

import argparse

from config import DEFAULT_TICKERS


def dedupe_upper(values: list[str]) -> list[str]:
    """Deduplicate and normalise a list of strings to uppercase, preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value).strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def parse_csv_values(values_arg: str | None) -> list[str]:
    """Split a comma-separated string into a deduplicated uppercase list."""
    if not values_arg:
        return []
    return dedupe_upper(values_arg.split(","))


def parse_ticker_list(tickers_arg: str | None) -> list[str]:
    """Return parsed tickers from a CLI arg or fall back to the configured default set."""
    if not tickers_arg:
        return list(DEFAULT_TICKERS.keys())
    return parse_csv_values(tickers_arg)


def resolve_target_tickers(
    tickers_arg: str | None,
    available_tickers: list[str] | None = None,
) -> list[str]:
    """Resolve the target ticker list from a CLI arg, active DB tickers, or the default universe."""
    if tickers_arg:
        return parse_ticker_list(tickers_arg)

    if available_tickers:
        resolved = dedupe_upper(available_tickers)
        if resolved:
            return resolved

    return list(DEFAULT_TICKERS.keys())


def filter_new_ticker_rows(rows: list[dict], existing_tickers: set[str]) -> list[dict]:
    """Return only the rows whose ticker is not already in existing_tickers."""
    return [row for row in rows if row["ticker"] not in existing_tickers]


def add_ticker_argument(parser: argparse.ArgumentParser) -> None:
    """Register a --tickers argument on the given parser."""
    parser.add_argument(
        "--tickers",
        help="Comma-separated list of tickers to process. If omitted, scripts can use the active DB universe and otherwise fall back to configured tickers.",
    )
