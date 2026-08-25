"""HTTP client for the Financial Modeling Prep (FMP) API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd

from services.http import JsonApiClient

# Calendar-day lookback per label — padded to account for weekends and holidays.
_PERIOD_DAY_MAP = {
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

_OHLCV_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]


class FMPClient(JsonApiClient):
    """Fetch ETF end-of-day prices, profile data, and holdings from Financial Modeling Prep."""

    def __init__(self, api_key: str, base_url: str, session: Any = None, **kwargs: Any) -> None:
        super().__init__(base_url=base_url, session=session, service_name="FMP", **kwargs)
        self.api_key = api_key

    def default_params(self) -> dict[str, str]:
        return {"apikey": self.api_key}

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
        rows = self._extract_rows(self.get_json("historical-price-eod/full", {"symbol": symbol}))
        if not rows:
            return pd.DataFrame(columns=["date", *_OHLCV_COLUMNS, "ticker"])

        frame = self._normalise_price_rows(rows, symbol)
        frame = self._with_dividend_adjusted_close(
            frame,
            symbol,
            period=period,
            start=start,
            end=end,
        )

        return self._trim_price_frame(frame, period=period, start=start, end=end)

    def get_security_profile(self, symbol: str) -> dict[str, Any]:
        """Return the FMP profile record for a symbol (company name, type, description, etc.)."""
        return self._extract_record(self.get_json("profile", {"symbol": symbol}))

    def get_etf_info(self, symbol: str) -> dict[str, Any]:
        """Return FMP ETF-specific metadata (expense ratio, AUM, category, etc.)."""
        return self._extract_record(self.get_json("etf/info", {"symbol": symbol}))

    def get_etf_holdings(self, symbol: str) -> list[dict[str, Any]]:
        """Return live ETF holdings rows for a symbol, or an empty list if unavailable."""
        rows = self._extract_rows(self.get_json(f"etf-holder/{symbol}", {}))
        if not rows:
            return []
        frame = pd.DataFrame(rows)
        if frame.empty:
            return []
        for col in ["weightPercentage", "weight", "sharesNumber", "marketValue"]:
            if col not in frame.columns:
                continue
            # errors="ignore" is deprecated; keep its all-or-nothing behaviour explicitly so a
            # column of genuinely non-numeric labels is passed through rather than blanked.
            try:
                frame[col] = pd.to_numeric(frame[col])
            except (TypeError, ValueError):
                continue
        holdings: list[dict[str, Any]] = frame.to_dict(orient="records")
        return holdings

    def get_economic_calendar(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return scheduled economic calendar events from FMP."""
        params = {}
        if start is not None:
            params["from"] = start
        if end is not None:
            params["to"] = end
        return self._extract_rows(self.get_json("economic-calendar", params))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalise_price_rows(self, rows: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
        """Return FMP price rows in the store-ready column shape."""
        frame = pd.DataFrame(rows).rename(columns={"symbol": "ticker", "adjClose": "adj_close"})
        for col in _OHLCV_COLUMNS:
            if col not in frame.columns:
                frame[col] = (
                    frame["close"] if col == "adj_close" and "close" in frame.columns else 0.0
                )
        if "close" in frame.columns:
            frame["adj_close"] = frame["adj_close"].fillna(frame["close"])

        frame["ticker"] = symbol.upper()
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        frame[_OHLCV_COLUMNS] = frame[_OHLCV_COLUMNS].apply(pd.to_numeric, errors="coerce")
        return (
            frame[["date", *_OHLCV_COLUMNS, "ticker"]]
            .dropna(subset=["date", *_OHLCV_COLUMNS])
            .sort_values("date")
            .reset_index(drop=True)
        )

    def _with_dividend_adjusted_close(
        self,
        frame: pd.DataFrame,
        symbol: str,
        *,
        period: str | None,
        start: str | None,
        end: str | None,
    ) -> pd.DataFrame:
        """Overlay dividend-adjusted close values from FMP when available."""
        rows = self._extract_rows(
            self.get_json(
                "historical-price-eod/dividend-adjusted",
                self._dividend_adjusted_params(symbol, period=period, start=start, end=end),
            )
        )
        if not rows:
            return frame

        adjusted = pd.DataFrame(rows).rename(columns={"adjClose": "adj_close"})
        if "date" not in adjusted.columns or "adj_close" not in adjusted.columns:
            return frame
        adjusted["date"] = pd.to_datetime(adjusted["date"]).dt.strftime("%Y-%m-%d")
        adjusted["adj_close"] = pd.to_numeric(adjusted["adj_close"], errors="coerce")
        adjusted = (
            adjusted[["date", "adj_close"]]
            .dropna(subset=["date", "adj_close"])
            .drop_duplicates(subset=["date"], keep="last")
        )
        if adjusted.empty:
            return frame

        merged = frame.merge(
            adjusted.rename(columns={"adj_close": "dividend_adj_close"}),
            on="date",
            how="left",
        )
        merged["adj_close"] = merged["dividend_adj_close"].fillna(merged["adj_close"])
        return merged.drop(columns=["dividend_adj_close"])

    def _dividend_adjusted_params(
        self,
        symbol: str,
        *,
        period: str | None,
        start: str | None,
        end: str | None,
    ) -> dict[str, str]:
        """Return request params for the dividend-adjusted endpoint."""
        params = {"symbol": symbol}
        if start is not None:
            params["from"] = start
        elif period is not None and (cutoff := self._period_cutoff(period)) is not None:
            params["from"] = cutoff
        if end is not None:
            params["to"] = end
        return params

    def _trim_price_frame(
        self,
        frame: pd.DataFrame,
        *,
        period: str | None,
        start: str | None,
        end: str | None,
    ) -> pd.DataFrame:
        """Apply period/start/end filters to a normalized price frame."""
        if start is not None:
            frame = frame.loc[frame["date"] >= str(start)]
        elif period is not None and (cutoff := self._period_cutoff(period)) is not None:
            frame = frame.loc[frame["date"] >= cutoff]
        if end is not None:
            frame = frame.loc[frame["date"] < str(end)]
        return frame.reset_index(drop=True)

    def _extract_rows(self, payload: Any) -> list[dict[str, Any]]:
        """Unwrap a list of rows from FMP's varied response shapes."""
        if isinstance(payload, dict):
            return payload.get("historical", []) or payload.get("data", []) or []
        if isinstance(payload, list):
            return payload
        return []

    def _extract_record(self, payload: Any) -> dict[str, Any]:
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
        return (datetime.now(UTC).date() - timedelta(days=lookback)).isoformat()
