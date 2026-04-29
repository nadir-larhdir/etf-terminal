"""HTTP client for the Federal Reserve Economic Data (FRED) API."""

from __future__ import annotations

import pandas as pd
import requests


class FredClient:
    """Fetch macroeconomic time series and metadata from the FRED REST API."""

    def __init__(self, api_key: str, base_url: str, session: requests.Session | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def get_series(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """Return a clean DataFrame of (date, value, series_id) for the given FRED series.

        Non-numeric values (e.g. FRED's '.' placeholder) are coerced to NaN and dropped.
        """
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start is not None:
            params["observation_start"] = str(start)
        if end is not None:
            params["observation_end"] = str(end)

        payload = self._request_json("series/observations", params)
        observations = payload.get("observations", []) if isinstance(payload, dict) else []

        if not observations:
            return pd.DataFrame(columns=["date", "value", "series_id"])

        frame = pd.DataFrame(observations)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
        frame["series_id"] = series_id
        frame = frame[["date", "value", "series_id"]]
        frame = frame.dropna(subset=["date", "value"])
        frame["value"] = frame["value"].astype(float)
        frame = frame.sort_values("date").reset_index(drop=True)
        return frame

    def get_series_metadata(self, series_id: str) -> dict[str, str]:
        """Return title, frequency, and units for a FRED series from the /series endpoint."""
        payload = self._request_json(
            "series",
            {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
            },
        )
        series_rows = payload.get("seriess", []) if isinstance(payload, dict) else []
        if not series_rows:
            return {}

        row = series_rows[0]
        return {
            "title": str(row.get("title", "")).strip(),
            "frequency": str(row.get("frequency", "")).strip(),
            "units": str(row.get("units", "")).strip(),
        }

    def _request_json(self, endpoint: str, params: dict) -> dict | list:
        """Execute a FRED GET request and return decoded JSON."""
        response = self.session.get(
            f"{self.base_url}/{endpoint.lstrip('/')}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
