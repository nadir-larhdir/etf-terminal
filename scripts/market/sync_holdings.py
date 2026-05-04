"""Fetch and persist daily ETF holdings snapshots."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fixed_income.etfs import ETFHoldings

logger = logging.getLogger(__name__)


def refresh_holdings_snapshots(holdings_store, tickers: list[str], *, as_of_date: str | None = None) -> int:
    """Fetch holdings for tickers and persist the parsed snapshots."""
    snapshot_date = as_of_date or datetime.now(UTC).date().isoformat()
    refreshed = 0
    for ticker in tickers:
        try:
            print(f"Fetching holdings for {ticker}...")
            frame = ETFHoldings(ticker).get()
            if frame.empty:
                logger.warning("No holdings returned for %s.", ticker)
                continue
            holdings_store.replace_holdings(ticker, frame, as_of_date=snapshot_date)
            refreshed += 1
        except Exception as exc:
            logger.warning("Holdings refresh failed for %s: %s", ticker, exc)
    return refreshed
