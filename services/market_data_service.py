from datetime import datetime
import pandas as pd
import yfinance as yf


class MarketDataService:
    def __init__(self, price_repository):
        self.price_repository = price_repository

    def backfill(self, tickers: list[str], period: str = "1y"):
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="column",
        )

        for ticker in tickers:
            if isinstance(raw.columns, pd.MultiIndex):
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
            frame["ticker"] = ticker
            frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
            frame["source"] = "yfinance"
            frame["updated_at"] = datetime.utcnow().isoformat()
            self.price_repository.replace_ticker_prices(ticker, frame)
