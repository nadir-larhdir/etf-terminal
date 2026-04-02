from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf


class MarketDataService:
    """Fetch ETF price history and synchronize it into the local database."""

    def __init__(self, price_repository):
        self.price_repository = price_repository

    def _fetch_history(
        self,
        tickers: list[str],
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        download_kwargs = {
            "tickers": tickers,
            "interval": "1d",
            "auto_adjust": False,
            "progress": False,
            "threads": True,
            "group_by": "column",
        }
        if start is not None:
            download_kwargs["start"] = start
        if end is not None:
            download_kwargs["end"] = end
        if start is None and period is not None:
            download_kwargs["period"] = period

        raw = yf.download(
            **download_kwargs,
        )
        return raw

    def _build_price_frame(self, raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()

        if isinstance(raw.columns, pd.MultiIndex):
            required_column = ("Open", ticker)
            if required_column not in raw.columns:
                return pd.DataFrame()

            frame = pd.DataFrame({
                "date": raw[("Open", ticker)].index,
                "open": raw[("Open", ticker)].values,
                "high": raw[("High", ticker)].values,
                "low": raw[("Low", ticker)].values,
                "close": raw[("Close", ticker)].values,
                "adj_close": raw[("Adj Close", ticker)].values if ("Adj Close", ticker) in raw.columns else raw[("Close", ticker)].values,
                "volume": raw[("Volume", ticker)].values,
            })
        else:
            frame = pd.DataFrame({
                "date": raw["Open"].index,
                "open": raw["Open"].values,
                "high": raw["High"].values,
                "low": raw["Low"].values,
                "close": raw["Close"].values,
                "adj_close": raw["Adj Close"].values if "Adj Close" in raw.columns else raw["Close"].values,
                "volume": raw["Volume"].values,
            })

        frame = frame.dropna().copy()
        if frame.empty:
            return frame

        frame["ticker"] = ticker
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        frame["source"] = "yfinance"
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
