from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import pandas as pd

from config import FMP_API_KEY, FMP_BASE_URL
from services.market.fmp_client import FMPClient


class MarketDataService:
    """Fetch ETF price history and synchronize it into the local database."""

    def __init__(self, price_store):
        self.price_store = price_store
        self.fmp_client = FMPClient(api_key=FMP_API_KEY, base_url=FMP_BASE_URL)

    def _fetch_history(
        self,
        tickers: list[str],
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"])

        # Bulk sync speed comes mostly from overlapping the network waits across tickers.
        frames: list[pd.DataFrame] = []
        max_workers = min(8, max(len(tickers), 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.fmp_client.get_historical_price_eod_full,
                    ticker,
                    period=period,
                    start=start,
                    end=end,
                ): ticker
                for ticker in tickers
            }
            for future in as_completed(futures):
                frame = future.result()
                if not frame.empty:
                    frames.append(frame)

        if not frames:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"]
            )

        return pd.concat(frames, ignore_index=True)

    def _build_price_frame(self, raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()
        frame = raw.loc[raw["ticker"].astype(str) == ticker].copy()
        if frame.empty:
            return frame

        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        frame["source"] = "fmp"
        frame["updated_at"] = datetime.utcnow().isoformat()
        return frame

    def sync_price_history(
        self,
        tickers: list[str],
        period: str = "1y",
        replace_existing: bool = True,
    ) -> None:
        raw = self._fetch_history(tickers=tickers, period=period)

        for ticker in tickers:
            frame = self._build_price_frame(raw, ticker)
            if frame.empty:
                continue

            if replace_existing:
                self.price_store.replace_ticker_prices(ticker, frame)
            else:
                self.price_store.upsert_prices(frame)

    def sync_price_gaps(self, tickers: list[str], period: str = "1y") -> None:
        self.sync_price_history(tickers=tickers, period=period, replace_existing=False)

    def sync_missing_ticker_history(self, tickers: list[str], period: str = "1y") -> list[str]:
        existing = self.price_store.get_existing_tickers(tickers)
        missing = [ticker for ticker in tickers if ticker not in existing]

        if missing:
            self.sync_price_history(tickers=missing, period=period, replace_existing=False)

        return missing

    def sync_incremental_updates(
        self,
        tickers: list[str],
        period_for_new: str = "1y",
        overlap_days: int = 5,
    ) -> dict[str, str]:
        latest_dates = self.price_store.get_latest_stored_dates(tickers)
        today = datetime.utcnow().date()
        statuses: dict[str, str] = {}
        new_tickers = [ticker for ticker in tickers if latest_dates.get(ticker) is None]
        existing_tickers = [ticker for ticker in tickers if latest_dates.get(ticker) is not None]

        if new_tickers:
            self.sync_price_history(new_tickers, period=period_for_new, replace_existing=False)
            statuses.update({ticker: f"initialized_{period_for_new}" for ticker in new_tickers})

        if not existing_tickers:
            return statuses

        start_dates = {
            ticker: (pd.to_datetime(latest_dates[ticker]).date() - timedelta(days=max(overlap_days, 0))).isoformat()
            for ticker in existing_tickers
        }
        end_date = (today + timedelta(days=1)).isoformat()
        earliest_start = min(start_dates.values())
        raw = self._fetch_history(tickers=existing_tickers, start=earliest_start, end=end_date)

        for ticker in existing_tickers:
            frame = self._build_price_frame(raw, ticker)
            if frame.empty:
                statuses[ticker] = "no_new_rows"
                continue

            self.price_store.upsert_prices(frame)
            statuses[ticker] = f"updated_from_{start_dates[ticker]}"

        return statuses
