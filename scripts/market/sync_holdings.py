"""Fetch and persist daily ETF holdings snapshots."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from fixed_income.etfs import ETFHoldings
from stores.market import HoldingsStore

logger = logging.getLogger(__name__)


def _refresh_one(engine, ticker: str, snapshot_date: str) -> bool:
    """Fetch and persist one ticker holdings snapshot."""
    print(f"Fetching holdings for {ticker}...")
    frame = ETFHoldings(ticker).get()
    if frame.empty:
        logger.warning("No holdings returned for %s.", ticker)
        return False
    HoldingsStore(engine).replace_holdings(ticker, frame, as_of_date=snapshot_date)
    return True


def refresh_holdings_snapshots(
    holdings_store, tickers: list[str], *, as_of_date: str | None = None
) -> int:
    """Fetch holdings for tickers and persist the parsed snapshots."""
    snapshot_date = as_of_date or datetime.now(UTC).date().isoformat()
    if not tickers:
        return 0

    refreshed = 0
    max_workers = min(8, len(tickers))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_refresh_one, holdings_store.engine, ticker, snapshot_date): ticker
            for ticker in tickers
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                refreshed += int(future.result())
            except Exception as exc:
                logger.warning("Holdings refresh failed for %s: %s", ticker, exc)
    return refreshed
