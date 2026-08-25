from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine

from fixed_income.analytics.result_models import (
    ETFAnalyticsSnapshot,
    RateRiskEstimate,
    SpreadRiskEstimate,
)
from stores.analytics.analytics_snapshot_store import AnalyticsSnapshotStore


def _snapshot(ticker: str = "LQD", *, duration: float | None = 6.4, with_spread: bool = True):
    return ETFAnalyticsSnapshot(
        ticker=ticker,
        asset_bucket="IG Credit",
        model_type_used="provider_metadata",
        confidence_level="high",
        notes="Duration is sourced from issuer metadata.",
        reason=None,
        rate_risk=RateRiskEstimate(
            estimated_duration=duration,
            dv01_per_share=None if duration is None else duration * 110.0 * 0.0001,
            observations_used=120,
        ),
        spread_risk=(
            SpreadRiskEstimate(
                beta_per_bp=-0.00012,
                dv01_proxy_per_share=0.0132,
                regression_r2=0.62,
                proxy_used="BAMLC0A0CM",
            )
            if with_spread
            else None
        ),
        as_of_date="2026-08-21",
        model_version="v1",
    )


@pytest.fixture
def store(engine: Engine) -> AnalyticsSnapshotStore:
    return AnalyticsSnapshotStore(engine)


def test_a_snapshot_round_trips_with_its_rate_and_spread_risk(
    store: AnalyticsSnapshotStore,
) -> None:
    store.upsert_snapshot(_snapshot(), as_of_date="2026-08-21")

    loaded = store.get_latest_snapshot("LQD")

    assert loaded is not None
    assert loaded.ticker == "LQD"
    assert loaded.estimated_duration == pytest.approx(6.4)
    assert loaded.spread_proxy_used == "BAMLC0A0CM"
    assert loaded.spread_model_r2 == pytest.approx(0.62)


def test_upserting_the_same_date_updates_rather_than_duplicating(
    store: AnalyticsSnapshotStore,
) -> None:
    store.upsert_snapshot(_snapshot(duration=6.4), as_of_date="2026-08-21")
    store.upsert_snapshot(_snapshot(duration=7.7), as_of_date="2026-08-21")

    loaded = store.get_latest_snapshot("LQD")

    assert loaded is not None and loaded.estimated_duration == pytest.approx(7.7)
    assert len(store.get_latest_snapshots(["LQD"])) == 1


def test_the_most_recent_date_wins(store: AnalyticsSnapshotStore) -> None:
    store.upsert_snapshot(_snapshot(duration=6.0), as_of_date="2026-08-20")
    store.upsert_snapshot(_snapshot(duration=6.9), as_of_date="2026-08-21")

    loaded = store.get_latest_snapshot("LQD")

    assert loaded is not None and loaded.estimated_duration == pytest.approx(6.9)


def test_an_unknown_symbol_has_no_snapshot(store: AnalyticsSnapshotStore) -> None:
    assert store.get_latest_snapshot("NOPE") is None


def test_a_snapshot_without_spread_risk_round_trips_as_none(
    store: AnalyticsSnapshotStore,
) -> None:
    store.upsert_snapshot(_snapshot(with_spread=False), as_of_date="2026-08-21")

    loaded = store.get_latest_snapshot("LQD")

    assert loaded is not None and loaded.spread_risk is None


def test_a_snapshot_with_no_duration_round_trips_as_none(store: AnalyticsSnapshotStore) -> None:
    store.upsert_snapshot(_snapshot(duration=None), as_of_date="2026-08-21")

    loaded = store.get_latest_snapshot("LQD")

    assert loaded is not None and loaded.estimated_duration is None


def test_an_upsert_stamps_updated_at(store: AnalyticsSnapshotStore) -> None:
    store.upsert_snapshot(_snapshot(), as_of_date="2026-08-21")

    loaded = store.get_latest_snapshot("LQD")

    assert loaded is not None and loaded.updated_at


def test_latest_snapshots_return_one_row_per_requested_symbol(
    store: AnalyticsSnapshotStore,
) -> None:
    store.upsert_snapshot(_snapshot("LQD"), as_of_date="2026-08-20")
    store.upsert_snapshot(_snapshot("LQD"), as_of_date="2026-08-21")
    store.upsert_snapshot(_snapshot("HYG"), as_of_date="2026-08-21")

    frame = store.get_latest_snapshots(["LQD", "HYG"])

    assert len(frame) == 2
    assert set(frame["symbol"]) == {"LQD", "HYG"}


def test_latest_snapshots_of_no_symbols_is_empty(store: AnalyticsSnapshotStore) -> None:
    assert store.get_latest_snapshots([]).empty
