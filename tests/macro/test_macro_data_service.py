from __future__ import annotations

from services.macro.macro_data_service import MacroDataService
from tests.fakes import FakeMacroClient, FakeMacroStore


def test_macro_data_service_incremental_fetch_plan_and_statuses() -> None:
    store = FakeMacroStore(latest_dates={"DGS10": "2024-01-10"})
    service = MacroDataService(FakeMacroClient(), store)

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
