from __future__ import annotations

import pandas as pd

from services.macro.macro_data_service import MacroDataService


class FakeFredClient:
    def get_series(self, series_id: str, *, start: str | None, end: str | None) -> pd.DataFrame:
        return pd.DataFrame([{"series_id": series_id, "date": start or "2024-01-01", "value": 1.0}])

    def get_series_metadata(self, series_id: str) -> dict[str, str]:
        return {"title": series_id, "frequency": "Daily", "units": "Percent"}


class FakeMacroStore:
    def __init__(self) -> None:
        self.latest_dates = {"DGS10": "2024-01-10", "DGS2": None}
        self.upserts: list[pd.DataFrame] = []

    def get_latest_stored_dates(self, series_ids: list[str]) -> dict[str, str | None]:
        return {series_id: self.latest_dates.get(series_id) for series_id in series_ids}

    def upsert_series(self, frame: pd.DataFrame) -> None:
        self.upserts.append(frame.copy())


def test_macro_data_service_incremental_fetch_plan_and_statuses() -> None:
    store = FakeMacroStore()
    service = MacroDataService(FakeFredClient(), store)

    statuses = service.sync_incremental_updates(
        ["DGS10", "DGS2"],
        overlap_days=3,
        default_start="2000-01-01",
        end="2024-01-12",
    )

    assert statuses == {
        "DGS10": "updated_from_2024-01-07",
        "DGS2": "initialized_from_2000-01-01",
    }
    assert len(store.upserts) == 2
    assert [frame["series_id"].iloc[0] for frame in store.upserts] == ["DGS10", "DGS2"]
