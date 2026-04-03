from __future__ import annotations

import pandas as pd
import requests


class FredClient:
    """Fetch macroeconomic time series from the FRED API."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def get_series(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start is not None:
            params["observation_start"] = str(start)
        if end is not None:
            params["observation_end"] = str(end)

        response = requests.get(
            f"{self.base_url}/series/observations",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
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
        response = requests.get(
            f"{self.base_url}/series",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        series_rows = payload.get("seriess", []) if isinstance(payload, dict) else []
        if not series_rows:
            return {}

        row = series_rows[0]
        return {
            "title": str(row.get("title", "")).strip(),
            "frequency": str(row.get("frequency", "")).strip(),
            "units": str(row.get("units", "")).strip(),
        }
