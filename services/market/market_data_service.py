from datetime import datetime, timedelta
import pandas as pd

from config import FMP_API_KEY, FMP_BASE_URL
from services.market.fmp_client import FMPClient


class MarketDataService:
    """Fetch ETF price history and synchronize it into the local database."""

    def __init__(self, price_repository):
        self.price_repository = price_repository
        self.fmp_client = FMPClient(api_key=FMP_API_KEY, base_url=FMP_BASE_URL)

    def _fetch_history(
        self,
        tickers: list[str],
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        frames = []
        for ticker in tickers:
            frame = self.fmp_client.get_historical_price_eod_full(
                ticker,
                period=period,
                start=start,
                end=end,
            )
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
    ):
        raw = self._fetch_history(tickers=tickers, period=period)

        for ticker in tickers:
            frame = self._build_price_frame(raw, ticker)
            if frame.empty:
                continue

            if replace_existing:
                self.price_repository.replace_ticker_prices(ticker, frame)
            else:
                self.price_repository.upsert_prices(frame)

    def sync_price_gaps(self, tickers: list[str], period: str = "1y"):
        self.sync_price_history(tickers=tickers, period=period, replace_existing=False)

    def sync_missing_ticker_history(self, tickers: list[str], period: str = "1y") -> list[str]:
        existing = self.price_repository.get_existing_tickers(tickers)
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
        latest_dates = self.price_repository.get_latest_stored_dates(tickers)
        today = datetime.utcnow().date()
        statuses: dict[str, str] = {}

        for ticker in tickers:
            latest_date = latest_dates.get(ticker)

            if latest_date is None:
                self.sync_price_history([ticker], period=period_for_new, replace_existing=False)
                statuses[ticker] = f"initialized_{period_for_new}"
                continue

            start_date = (
                pd.to_datetime(latest_date).date() - timedelta(days=max(overlap_days, 0))
            ).isoformat()
            end_date = (today + timedelta(days=1)).isoformat()
            raw = self._fetch_history(tickers=[ticker], start=start_date, end=end_date)
            frame = self._build_price_frame(raw, ticker)

            if frame.empty:
                statuses[ticker] = "no_new_rows"
                continue

            self.price_repository.upsert_prices(frame)
            statuses[ticker] = f"updated_from_{start_date}"

        return statuses
