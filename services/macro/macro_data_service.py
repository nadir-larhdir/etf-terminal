"""Orchestrate fetching FRED series and persisting them via MacroStore."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from config import MACRO_SERIES_REGISTRY

# Re-exported alias kept for backwards compatibility with scripts that import it directly.
DEFAULT_MACRO_SERIES: dict = MACRO_SERIES_REGISTRY


class MacroDataService:
    """Fetch and sync macroeconomic time series from FRED into the data store."""

    BASE_COLUMNS = [
        "series_id",
        "date",
        "value",
        "series_name",
        "category",
        "sub_category",
        "frequency",
        "units",
        "source",
        "is_active",
        "last_updated_at",
    ]

    def __init__(self, fred_client, macro_store=None):
        self.fred = fred_client
        self.macro_store = macro_store

    def sync_series_history(
        self,
        series_ids: list[str],
        start: str | None = None,
        end: str | None = None,
        replace_existing: bool = True,
    ) -> None:
        """Fetch and write a full or partial history window for each series."""
        self._require_store()
        for series_id in series_ids:
            frame = self._fetch_series_frame(series_id, start=start, end=end)
            self._write_series_frame(series_id, frame, replace_existing=replace_existing)

    def sync_incremental_updates(
        self,
        series_ids: list[str],
        overlap_days: int = 7,
        default_start: str | None = "2000-01-01",
        end: str | None = None,
    ) -> dict[str, str]:
        """Fetch only new observations for each series, initialising missing ones from default_start."""
        self._require_store()
        latest_dates = self.macro_store.get_latest_stored_dates(series_ids)
        effective_end = end or datetime.utcnow().date().isoformat()
        statuses: dict[str, str] = {}

        for series_id in series_ids:
            latest_date = latest_dates.get(series_id)
            if latest_date is None:
                frame = self._fetch_series_frame(series_id, start=default_start, end=effective_end)
                if frame.empty:
                    statuses[series_id] = "no_rows_returned"
                    continue
                self._write_series_frame(series_id, frame, replace_existing=False)
                statuses[series_id] = f"initialized_from_{default_start}"
                continue

            start_date = (
                pd.to_datetime(latest_date).date() - timedelta(days=max(overlap_days, 0))
            ).isoformat()
            frame = self._fetch_series_frame(series_id, start=start_date, end=effective_end)
            if frame.empty:
                statuses[series_id] = "no_new_rows"
                continue
            self._write_series_frame(series_id, frame, replace_existing=False)
            statuses[series_id] = f"updated_from_{start_date}"

        return statuses

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_store(self) -> None:
        """Raise if no macro_store was injected — required for all write operations."""
        if self.macro_store is None:
            raise ValueError("MacroDataService requires a macro_store for sync operations.")

    def _resolve_series_details(self, series_id: str) -> dict[str, str]:
        """Merge registry metadata with live FRED metadata, preferring the registry."""
        registry = MACRO_SERIES_REGISTRY.get(series_id, {})
        metadata = self.fred.get_series_metadata(series_id)
        return {
            "series_name": registry.get("name") or metadata.get("title", ""),
            "category": registry.get("category", ""),
            "sub_category": registry.get("sub_category", ""),
            "frequency": registry.get("frequency") or metadata.get("frequency", ""),
            "units": registry.get("units") or metadata.get("units", ""),
        }

    def _build_series_frame(self, raw: pd.DataFrame, series_id: str) -> pd.DataFrame:
        """Enrich a raw FRED observations frame with series metadata columns."""
        if raw.empty:
            return pd.DataFrame(columns=self.BASE_COLUMNS)
        frame = raw.loc[raw["series_id"].astype(str) == series_id].copy()
        if frame.empty:
            return pd.DataFrame(columns=self.BASE_COLUMNS)
        details = self._resolve_series_details(series_id)
        frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
        frame["series_name"] = details["series_name"]
        frame["category"] = details["category"]
        frame["sub_category"] = details["sub_category"]
        frame["frequency"] = details["frequency"]
        frame["units"] = details["units"]
        frame["source"] = "fred"
        frame["is_active"] = 1
        frame["last_updated_at"] = datetime.utcnow().isoformat()
        return frame[self.BASE_COLUMNS]

    def _fetch_series_frame(
        self, series_id: str, *, start: str | None, end: str | None
    ) -> pd.DataFrame:
        """Fetch and enrich a single FRED series frame."""
        raw = self.fred.get_series(series_id, start=start, end=end)
        return self._build_series_frame(raw, series_id)

    def _write_series_frame(
        self, series_id: str, frame: pd.DataFrame, *, replace_existing: bool
    ) -> None:
        """Persist a series frame using replace or upsert depending on replace_existing."""
        if frame.empty:
            return
        if replace_existing:
            self.macro_store.replace_series(series_id, frame)
        else:
            self.macro_store.upsert_series(frame)
