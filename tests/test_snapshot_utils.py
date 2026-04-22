from fixed_income.analytics.result_models import RateRiskEstimate, SecurityAnalyticsSnapshot
from fixed_income.analytics.snapshot_utils import is_snapshot_stale


def _snapshot(*, estimated_duration: float | None, as_of_date: str = "2026-04-22") -> SecurityAnalyticsSnapshot:
    return SecurityAnalyticsSnapshot(
        ticker="LQD",
        asset_bucket="Investment Grade Credit",
        model_type_used="treasury_etf_benchmark_regression",
        confidence_level="high",
        notes="",
        reason=None,
        rate_risk=RateRiskEstimate(
            estimated_duration=estimated_duration,
            dv01_per_share=0.08,
            regression_r2=0.8,
            benchmark_beta=None,
            benchmark_used="IEF",
            rate_proxy_used="Treasury ETF benchmark",
            lookback_days_used=120,
            observations_used=100,
        ),
        as_of_date=as_of_date,
        updated_at="2026-04-22T12:00:00",
    )


def test_snapshot_is_stale_when_metadata_duration_changes() -> None:
    snapshot = _snapshot(estimated_duration=8.2)

    assert is_snapshot_stale(
        snapshot,
        now="2026-04-22T13:00:00",
        ttl_hours=24,
        required_as_of_date="2026-04-22",
        required_estimated_duration=8.0,
    )


def test_snapshot_is_fresh_when_metadata_duration_matches() -> None:
    snapshot = _snapshot(estimated_duration=8.0)

    assert not is_snapshot_stale(
        snapshot,
        now="2026-04-22T13:00:00",
        ttl_hours=24,
        required_as_of_date="2026-04-22",
        required_estimated_duration=8.0,
    )
