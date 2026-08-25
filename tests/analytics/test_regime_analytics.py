from __future__ import annotations

import pandas as pd
import pytest

from fixed_income.analytics.regime_analytics import RegimeAnalytics
from tests.fakes import FakeMacroFeatureStore

DATES = pd.bdate_range("2026-06-01", periods=40)


def _matrix(**series: float | list[float]) -> pd.DataFrame:
    data = {
        name: ([value] * len(DATES) if isinstance(value, int | float) else value)
        for name, value in series.items()
    }
    return pd.DataFrame(data, index=DATES)


def _analytics(matrix: pd.DataFrame | None = None) -> RegimeAnalytics:
    return RegimeAnalytics(FakeMacroFeatureStore(matrix))


def _all_features(value: float) -> pd.DataFrame:
    return _matrix(HY_OAS_Z60=value, IG_OAS_Z60=value, UST_2S10S_Z60=value)


def test_wide_spreads_and_a_flattening_curve_read_risk_off() -> None:
    # Spreads carry a negative sign, so positive spread z-scores are risk-off.
    matrix = _matrix(HY_OAS_Z60=2.0, IG_OAS_Z60=2.0, UST_2S10S_Z60=-2.0)

    assert _analytics(matrix).current_regime().label == "Risk Off"


def test_tight_spreads_and_a_steepening_curve_read_risk_on() -> None:
    matrix = _matrix(HY_OAS_Z60=-2.0, IG_OAS_Z60=-2.0, UST_2S10S_Z60=2.0)

    assert _analytics(matrix).current_regime().label == "Risk On"


def test_features_at_their_own_average_read_neutral() -> None:
    assert _analytics(_all_features(0.0)).current_regime().label == "Neutral"


def test_an_empty_feature_store_reads_neutral_rather_than_failing() -> None:
    snapshot = _analytics().current_regime()

    assert snapshot.label == "Neutral"
    assert snapshot.composite_zscore == 0.0


def test_a_matrix_missing_every_configured_feature_reads_neutral() -> None:
    assert _analytics(_matrix(SOMETHING_ELSE=1.0)).current_regime().label == "Neutral"


def test_the_composite_is_built_from_whichever_features_are_present() -> None:
    partial = _matrix(HY_OAS_Z60=-1.5)

    assert _analytics(partial).current_regime().label == "Risk On"


def test_spread_widening_and_curve_steepening_offset_each_other() -> None:
    matrix = _matrix(HY_OAS_Z60=1.0, IG_OAS_Z60=1.0, UST_2S10S_Z60=1.0)

    snapshot = _analytics(matrix).current_regime()

    assert snapshot.label == "Neutral"
    assert snapshot.composite_zscore == pytest.approx(-1.0 / 3.0, abs=0.05)


@pytest.mark.parametrize(
    ("zscore", "label"),
    [
        (-0.51, "Risk Off"),
        (-0.50, "Risk Off"),
        (-0.49, "Neutral"),
        (0.49, "Neutral"),
        (0.50, "Risk On"),
        (0.51, "Risk On"),
    ],
)
def test_thresholds_are_inclusive_at_the_boundary(zscore: float, label: str) -> None:
    assert _analytics()._bucket(zscore).label == label


def test_the_gauge_marker_stays_inside_the_bar_for_extreme_readings() -> None:
    for zscore in (-100.0, -2.0, 0.0, 2.0, 100.0):
        assert 0.0 <= _analytics()._bucket(zscore).position <= 100.0


def test_the_gauge_centres_at_a_zero_composite() -> None:
    assert _analytics()._bucket(0.0).position == pytest.approx(50.0)


def test_the_gauge_moves_monotonically_with_the_composite() -> None:
    positions = [_analytics()._bucket(z).position for z in (-2.0, -1.0, 0.0, 1.0, 2.0)]

    assert positions == sorted(positions)


@pytest.mark.parametrize(
    ("spike", "flips"),
    [(2.0, False), (2.5, False), (3.5, True)],
    ids=["two-sigma-day-held", "two-and-a-half-sigma-day-held", "extreme-day-flips"],
)
def test_one_noisy_day_cannot_flip_the_label_on_its_own(spike: float, flips: bool) -> None:
    """The whole point of the smoothing: a single session, however loud, should not
    reclassify the market. Only a genuinely extreme print gets through unaided."""
    calm = [0.0] * 39
    matrix = _matrix(
        HY_OAS_Z60=calm + [-spike],
        IG_OAS_Z60=calm + [-spike],
        UST_2S10S_Z60=calm + [spike],
    )

    label = _analytics(matrix).current_regime().label

    assert (label == "Risk On") is flips


def test_a_move_half_the_size_of_an_unaided_flip_still_lands_within_a_few_sessions() -> None:
    calm = [0.0] * 35
    matrix = _matrix(
        HY_OAS_Z60=calm + [-1.4] * 5,
        IG_OAS_Z60=calm + [-1.4] * 5,
        UST_2S10S_Z60=calm + [1.4] * 5,
    )

    assert _analytics(matrix).current_regime().label == "Risk On"


def test_a_sustained_move_does_flip_the_label() -> None:
    sustained = [0.0] * 30 + [-4.0] * 10
    matrix = _matrix(
        HY_OAS_Z60=sustained,
        IG_OAS_Z60=sustained,
        UST_2S10S_Z60=[0.0] * 30 + [4.0] * 10,
    )

    assert _analytics(matrix).current_regime().label == "Risk On"


def test_the_composite_of_an_empty_matrix_is_an_empty_series() -> None:
    assert _analytics().composite_zscore(pd.DataFrame()).empty


def test_rows_where_every_feature_is_missing_are_dropped() -> None:
    matrix = _matrix(HY_OAS_Z60=[float("nan")] * 39 + [-2.0])

    composite = _analytics().composite_zscore(matrix)

    assert len(composite) == 1
