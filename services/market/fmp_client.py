"""HTTP client for the Financial Modeling Prep (FMP) API."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import requests

# Calendar-day lookback per label — padded to account for weekends and holidays.
_PERIOD_DAY_MAP = {
    "5d": 7, "10d": 14, "30d": 45, "3m": 100, "6m": 190,
    "1y": 370, "2y": 740, "5y": 1850, "10y": 3700,
}

_OHLCV_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


class FMPClient:
    """Fetch ETF end-of-day prices, profile data, and holdings from Financial Modeling Prep."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    def get_historical_price_eod_full(
        self,
        symbol: str,
        *,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Return a cleaned OHLCV DataFrame for symbol, optionally trimmed by period or date range.

        Prefers start/end over period when both are provided.
        Returns an empty DataFrame (with correct columns) when FMP returns no rows.
        """
        rows = self._extract_rows(
            self._request_json("historical-price-eod/full", {"symbol": symbol})
        )
        if not rows:
            return pd.DataFrame(columns=["date", *_OHLCV_COLUMNS, "ticker"])

        frame = pd.DataFrame(rows).rename(columns={"symbol": "ticker", "adjClose": "adj_close"})
        for col in _OHLCV_COLUMNS:
            if col not in frame.columns:
                frame[col] = frame["close"] if col == "adj_close" and "close" in frame.columns else 0.0

        frame["ticker"] = symbol.upper()
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        for col in _OHLCV_COLUMNS:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").astype(float)

        frame = (
            frame[["date", *_OHLCV_COLUMNS, "ticker"]]
            .dropna(subset=["date", *_OHLCV_COLUMNS])
            .sort_values("date")
            .reset_index(drop=True)
        )

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
        """Return the FMP profile record for a symbol (company name, type, description, etc.)."""
        return self._extract_record(self._request_json("profile", {"symbol": symbol}))

    def get_etf_info(self, symbol: str) -> dict:
        """Return FMP ETF-specific metadata (expense ratio, AUM, category, etc.)."""
        return self._extract_record(self._request_json("etf/info", {"symbol": symbol}))

    def get_etf_holdings(self, symbol: str) -> list[dict]:
        """Return live ETF holdings rows for a symbol, or an empty list if unavailable."""
        rows = self._extract_rows(self._request_json(f"etf-holder/{symbol}", {}))
        if not rows:
            return []
        frame = pd.DataFrame(rows)
        if frame.empty:
            return []
        for col in ["weightPercentage", "weight", "sharesNumber", "marketValue"]:
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="ignore")
        return frame.to_dict(orient="records")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _request_json(self, endpoint: str, params: dict) -> dict | list:
        """Execute a GET request and return the parsed JSON response."""
        response = requests.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            params={**params, "apikey": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _extract_rows(self, payload: dict | list) -> list[dict]:
        """Unwrap a list of rows from FMP's varied response shapes."""
        if isinstance(payload, dict):
            return payload.get("historical", []) or payload.get("data", []) or []
        if isinstance(payload, list):
            return payload
        return []

    def _extract_record(self, payload: dict | list) -> dict:
        """Return the first record from FMP's single-item response shapes."""
        if isinstance(payload, list):
            return payload[0] if payload else {}
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return data[0] if data else {}
            return payload
        return {}

    def _period_cutoff(self, period: str) -> str | None:
        """Return the ISO cutoff date for a human-readable period string, or None if unrecognised."""
        lookback = _PERIOD_DAY_MAP.get(str(period).strip().lower())
        if lookback is None:
            return None
        return (datetime.utcnow().date() - timedelta(days=lookback)).isoformat()
