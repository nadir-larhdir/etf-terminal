"""Orchestrate fetching FMP price history and persisting it via PriceStore."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd

from config import FMP_API_KEY, FMP_BASE_URL
from services.market.fmp_client import FMPClient

_EMPTY_PRICE_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"]


class MarketDataService:
    """Fetch ETF price history from FMP and synchronise it into the price store."""

    def __init__(self, price_store):
        self.price_store = price_store
        self.fmp_client = FMPClient(api_key=FMP_API_KEY, base_url=FMP_BASE_URL)

    # ------------------------------------------------------------------
    # Public sync operations
    # ------------------------------------------------------------------

    def sync_price_history(
        self, tickers: list[str], period: str = "1y", replace_existing: bool = True
    ) -> None:
        """Fetch and persist a full history window for each ticker.

        If replace_existing is True, existing rows for each ticker are deleted first.
        """
        raw = self._fetch_history(tickers=tickers, period=period)
        for ticker in tickers:
            frame = self._build_price_frame(raw, ticker)
            self._persist_price_frame(ticker, frame, replace_existing=replace_existing)

    def sync_price_gaps(self, tickers: list[str], period: str = "1y") -> None:
        """Upsert prices without deleting existing rows — use to fill gaps without overwriting."""
        self.sync_price_history(tickers=tickers, period=period, replace_existing=False)

    def sync_missing_ticker_history(self, tickers: list[str], period: str = "1y") -> list[str]:
        """Initialise price history only for tickers that have no stored rows yet."""
        existing = self.price_store.get_existing_tickers(tickers)
        missing = [t for t in tickers if t not in existing]
        if missing:
            self.sync_price_history(tickers=missing, period=period, replace_existing=False)
        return missing

    def sync_incremental_updates(
        self,
        tickers: list[str],
        period_for_new: str = "1y",
        overlap_days: int = 5,
    ) -> dict[str, str]:
        """Fetch only new bars for existing tickers and initialise any new ones.

        Uses a shared earliest-start fetch to minimise API round trips, then
        filters each ticker's rows before persisting. Returns a status dict.
        """
        latest_dates = self.price_store.get_latest_stored_dates(tickers)
        today = datetime.utcnow().date()
        statuses: dict[str, str] = {}

        new_tickers = [t for t in tickers if latest_dates.get(t) is None]
        existing_tickers = [t for t in tickers if latest_dates.get(t) is not None]

        if new_tickers:
            self.sync_price_history(new_tickers, period=period_for_new, replace_existing=False)
            statuses.update({t: f"initialized_{period_for_new}" for t in new_tickers})

        if not existing_tickers:
            return statuses

        # Fetch a single date window covering all existing tickers at once.
        start_dates = {
            t: (pd.to_datetime(latest_dates[t]).date() - timedelta(days=max(overlap_days, 0))).isoformat()
            for t in existing_tickers
        }
        end_date = (today + timedelta(days=1)).isoformat()
        raw = self._fetch_history(tickers=existing_tickers, start=min(start_dates.values()), end=end_date)

        for ticker in existing_tickers:
            frame = self._build_price_frame(raw, ticker)
            if not self._persist_price_frame(ticker, frame, replace_existing=False):
                statuses[ticker] = "no_new_rows"
                continue
            statuses[ticker] = f"updated_from_{start_dates[ticker]}"

        return statuses

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_history(
        self,
        tickers: list[str],
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Fetch price history for multiple tickers concurrently and return a combined frame."""
        if not tickers:
            return pd.DataFrame(columns=_EMPTY_PRICE_COLUMNS)

        frames: list[pd.DataFrame] = []
        with ThreadPoolExecutor(max_workers=min(8, len(tickers))) as executor:
            futures = {
                executor.submit(self.fmp_client.get_historical_price_eod_full, t, period=period, start=start, end=end): t
                for t in tickers
            }
            for future in as_completed(futures):
                frame = future.result()
                if not frame.empty:
                    frames.append(frame)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=_EMPTY_PRICE_COLUMNS)

    def _build_price_frame(self, raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Slice the combined raw frame for one ticker and stamp source/updated_at."""
        if raw.empty:
            return pd.DataFrame()
        frame = raw.loc[raw["ticker"].astype(str) == ticker].copy()
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        frame["source"] = "fmp"
        frame["updated_at"] = datetime.utcnow().isoformat()
        return frame

    def _persist_price_frame(self, ticker: str, frame: pd.DataFrame, *, replace_existing: bool) -> bool:
        """Write a price frame to the store; returns False when the frame is empty."""
        if frame.empty:
            return False
        if replace_existing:
            self.price_store.replace_ticker_prices(ticker, frame)
        else:
            self.price_store.upsert_prices(frame)
        return True
