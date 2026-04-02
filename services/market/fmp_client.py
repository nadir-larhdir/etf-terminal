from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import requests


class FMPClient:
    """Fetch daily ETF pricing and basic profile data from Financial Modeling Prep."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def get_historical_price_eod_full(
        self,
        symbol: str,
        *,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        response = requests.get(
            f"{self.base_url}/historical-price-eod/full",
            params={
                "symbol": symbol,
                "apikey": self.api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict):
            rows = payload.get("historical", []) or payload.get("data", []) or []
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []

        if not rows:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"]
            )

        frame = pd.DataFrame(rows)
        frame = frame.rename(
            columns={
                "symbol": "ticker",
                "adjClose": "adj_close",
            }
        )

        for column in ["open", "high", "low", "close", "adj_close", "volume"]:
            if column not in frame.columns:
                if column == "adj_close" and "close" in frame.columns:
                    frame[column] = frame["close"]
                else:
                    frame[column] = 0.0

        frame["ticker"] = symbol.upper()
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")

        for column in ["open", "high", "low", "close", "adj_close", "volume"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)

        frame = frame[["date", "open", "high", "low", "close", "adj_close", "volume", "ticker"]]
        frame = frame.dropna(subset=["date", "open", "high", "low", "close", "adj_close", "volume"])
        frame = frame.sort_values("date").reset_index(drop=True)

        if start is not None:
            frame = frame.loc[frame["date"] >= str(start)].copy()
        elif period is not None:
            cutoff = self._period_cutoff(period)
            if cutoff is not None:
                frame = frame.loc[frame["date"] >= cutoff].copy()

        if end is not None:
            frame = frame.loc[frame["date"] < str(end)].copy()

        return frame.reset_index(drop=True)

    def get_security_profile(self, symbol: str) -> dict:
        response = requests.get(
            f"{self.base_url}/profile",
            params={
                "symbol": symbol,
                "apikey": self.api_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data[0] if data else {}
            return payload
        return {}

    def _period_cutoff(self, period: str) -> str | None:
        today = datetime.utcnow().date()
        period_key = str(period).strip().lower()
        day_map = {
            "5d": 7,
            "10d": 14,
            "30d": 45,
            "3m": 100,
            "6m": 190,
            "1y": 370,
            "2y": 740,
            "5y": 1850,
            "10y": 3700,
        }
        lookback_days = day_map.get(period_key)
        if lookback_days is None:
            return None
        return (today - timedelta(days=lookback_days)).isoformat()
