from datetime import datetime, timedelta

import pandas as pd

from config import MACRO_SERIES_REGISTRY

"""Default FRED series used by the terminal's macro layer."""
DEFAULT_MACRO_SERIES = MACRO_SERIES_REGISTRY


class MacroDataService:
    """Provide grouped macro datasets used by the terminal's market-context layer."""

    def __init__(self, fred_client, macro_repository=None):
        self.fred = fred_client
        self.macro_repository = macro_repository

    def get_treasury_curve(self):
        return {
            "2Y": self.fred.get_series("DGS2"),
            "10Y": self.fred.get_series("DGS10"),
            "30Y": self.fred.get_series("DGS30"),
        }

    def get_inflation(self):
        return self.fred.get_series("CPIAUCSL")

    def _resolve_series_details(self, series_id: str) -> dict[str, str]:
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
        if raw.empty:
            return pd.DataFrame(
                columns=[
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
            )

        frame = raw.loc[raw["series_id"].astype(str) == series_id].copy()
        if frame.empty:
            return pd.DataFrame(
                columns=[
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
            )

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
        return frame[
            [
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
        ]

    def sync_series_history(
        self,
        series_ids: list[str],
        start: str | None = None,
        end: str | None = None,
        replace_existing: bool = True,
    ):
        if self.macro_repository is None:
            raise ValueError("Macro repository is required for sync operations.")

        for series_id in series_ids:
            raw = self.fred.get_series(series_id, start=start, end=end)
            frame = self._build_series_frame(raw, series_id)
            if frame.empty:
                continue

            if replace_existing:
                self.macro_repository.replace_series(series_id, frame)
            else:
                self.macro_repository.upsert_series(frame)

    def sync_incremental_updates(
        self,
        series_ids: list[str],
        overlap_days: int = 7,
        default_start: str | None = "2000-01-01",
        end: str | None = None,
    ) -> dict[str, str]:
        if self.macro_repository is None:
            raise ValueError("Macro repository is required for sync operations.")

        latest_dates = self.macro_repository.get_latest_stored_dates(series_ids)
        statuses: dict[str, str] = {}
        effective_end = end or datetime.utcnow().date().isoformat()

        for series_id in series_ids:
            latest_date = latest_dates.get(series_id)
            if latest_date is None:
                raw = self.fred.get_series(series_id, start=default_start, end=effective_end)
                frame = self._build_series_frame(raw, series_id)
                if frame.empty:
                    statuses[series_id] = "no_rows_returned"
                    continue
                self.macro_repository.upsert_series(frame)
                statuses[series_id] = f"initialized_from_{default_start}"
                continue

            start_date = (
                pd.to_datetime(latest_date).date() - timedelta(days=max(overlap_days, 0))
            ).isoformat()
            raw = self.fred.get_series(series_id, start=start_date, end=effective_end)
            frame = self._build_series_frame(raw, series_id)

            if frame.empty:
                statuses[series_id] = "no_new_rows"
                continue

            self.macro_repository.upsert_series(frame)
            statuses[series_id] = f"updated_from_{start_date}"

        return statuses
