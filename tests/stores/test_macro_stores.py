from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from stores.macro.macro_feature_store import MacroFeatureStore
from stores.macro.macro_store import MacroStore


def _observations(series_id: str, dates: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"series_id": series_id, "date": date, "value": value}
            for date, value in zip(dates, values, strict=True)
        ]
    )


def _features(name: str, dates: list[str], values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "feature_name": name,
                "date": date,
                "value": value,
                "category": "Rates",
                "sub_category": "Curve",
                "source": "test",
                "last_updated_at": "2024-01-01T00:00:00",
            }
            for date, value in zip(dates, values, strict=True)
        ]
    )


@pytest.fixture
def macro(engine: Engine) -> MacroStore:
    return MacroStore(engine)


@pytest.fixture
def features(engine: Engine) -> MacroFeatureStore:
    return MacroFeatureStore(engine)


# ── MacroStore ──────────────────────────────────────────────────────────────


def test_observations_round_trip_as_a_date_indexed_history(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02", "2024-01-03"], [4.0, 4.1]))

    history = macro.get_series_history("DGS10")

    assert len(history) == 2
    assert float(history["value"].iloc[-1]) == 4.1


def test_upserting_the_same_observation_updates_it(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02"], [4.0]))
    macro.upsert_series(_observations("DGS10", ["2024-01-02"], [9.9]))

    history = macro.get_series_history("DGS10")

    assert len(history) == 1
    assert float(history["value"].iloc[0]) == 9.9


def test_upserting_an_empty_frame_is_a_no_op(macro: MacroStore) -> None:
    macro.upsert_series(pd.DataFrame())

    assert macro.get_latest_stored_dates() == {}


def test_series_history_can_be_bounded_by_date(macro: MacroStore) -> None:
    macro.upsert_series(
        _observations("DGS10", ["2024-01-02", "2024-01-03", "2024-01-04"], [4.0, 4.1, 4.2])
    )

    assert len(macro.get_series_history("DGS10", "2024-01-03", "2024-01-03")) == 1


def test_latest_stored_dates_report_the_newest_row_per_series(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02", "2024-01-05"], [4.0, 4.1]))
    macro.upsert_series(_observations("DGS2", ["2024-01-03"], [4.5]))

    assert macro.get_latest_stored_dates() == {"DGS10": "2024-01-05", "DGS2": "2024-01-03"}


def test_the_series_matrix_pivots_series_into_columns(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02", "2024-01-03"], [4.0, 4.1]))
    macro.upsert_series(_observations("DGS2", ["2024-01-02", "2024-01-03"], [4.5, 4.6]))

    matrix = macro.get_series_matrix(["DGS10", "DGS2"])

    assert sorted(matrix.columns) == ["DGS10", "DGS2"]
    assert len(matrix) == 2


def test_the_series_matrix_aligns_series_with_different_calendars(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02", "2024-01-03"], [4.0, 4.1]))
    macro.upsert_series(_observations("CPI", ["2024-01-02"], [300.0]))

    matrix = macro.get_series_matrix(["DGS10", "CPI"])

    assert len(matrix) == 2
    assert pd.isna(matrix["CPI"].iloc[-1])


def test_the_series_matrix_is_empty_when_nothing_is_stored(macro: MacroStore) -> None:
    assert macro.get_series_matrix(["DGS10"]).empty


def test_replacing_a_series_discards_its_previous_observations(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02", "2024-01-03"], [4.0, 4.1]))

    macro.replace_series("DGS10", _observations("DGS10", ["2024-02-01"], [5.0]))

    history = macro.get_series_history("DGS10")
    assert len(history) == 1
    assert float(history["value"].iloc[0]) == 5.0


def test_replacing_one_series_leaves_the_others_alone(macro: MacroStore) -> None:
    macro.upsert_series(_observations("DGS10", ["2024-01-02"], [4.0]))
    macro.upsert_series(_observations("DGS2", ["2024-01-02"], [4.5]))

    macro.replace_series("DGS10", _observations("DGS10", ["2024-02-01"], [5.0]))

    assert len(macro.get_series_history("DGS2")) == 1


# ── MacroFeatureStore ───────────────────────────────────────────────────────


def test_features_round_trip_into_a_wide_matrix(features: MacroFeatureStore) -> None:
    features.upsert_features(_features("UST_2S10S", ["2024-01-02", "2024-01-03"], [0.4, 0.5]))

    matrix = features.get_feature_matrix(["UST_2S10S"])

    assert list(matrix.columns) == ["UST_2S10S"]
    assert float(matrix["UST_2S10S"].iloc[-1]) == 0.5


def test_upserting_the_same_feature_date_updates_it(features: MacroFeatureStore) -> None:
    features.upsert_features(_features("UST_2S10S", ["2024-01-02"], [0.4]))
    features.upsert_features(_features("UST_2S10S", ["2024-01-02"], [0.9]))

    matrix = features.get_feature_matrix(["UST_2S10S"])

    assert len(matrix) == 1
    assert float(matrix["UST_2S10S"].iloc[0]) == 0.9


def test_upserting_no_features_is_a_no_op(features: MacroFeatureStore) -> None:
    features.upsert_features(pd.DataFrame())

    assert features.get_latest_feature_date() is None


def test_the_latest_feature_date_is_the_newest_across_all_features(
    features: MacroFeatureStore,
) -> None:
    features.upsert_features(_features("A", ["2024-01-02"], [1.0]))
    features.upsert_features(_features("B", ["2024-03-05"], [2.0]))

    assert features.get_latest_feature_date() == "2024-03-05"


def test_latest_feature_values_return_the_most_recent_row_per_feature(
    features: MacroFeatureStore,
) -> None:
    features.upsert_features(_features("A", ["2024-01-02", "2024-01-09"], [1.0, 3.0]))

    latest = features.get_latest_feature_values(["A"])

    assert len(latest) == 1
    assert float(latest.iloc[0]["value"]) == 3.0


def test_latest_feature_values_of_no_names_is_empty(features: MacroFeatureStore) -> None:
    assert features.get_latest_feature_values([]).empty


def test_feature_counts_report_rows_per_feature(features: MacroFeatureStore) -> None:
    features.upsert_features(_features("A", ["2024-01-02", "2024-01-03"], [1.0, 2.0]))
    features.upsert_features(_features("B", ["2024-01-02"], [1.0]))

    counts = features.get_feature_counts().set_index("feature_name")["row_count"]

    assert counts["A"] == 2 and counts["B"] == 1


def test_deleting_a_date_range_removes_only_those_rows(features: MacroFeatureStore) -> None:
    features.upsert_features(
        _features("A", ["2024-01-02", "2024-01-03", "2024-01-04"], [1.0, 2.0, 3.0])
    )

    features.delete_features(start_date="2024-01-03", end_date="2024-01-03")

    assert len(features.get_feature_matrix(["A"])) == 2


def test_deleting_without_bounds_clears_the_table(features: MacroFeatureStore) -> None:
    features.upsert_features(_features("A", ["2024-01-02"], [1.0]))

    features.delete_features()

    assert features.get_latest_feature_date() is None


def test_the_feature_matrix_is_empty_when_nothing_is_stored(features: MacroFeatureStore) -> None:
    assert features.get_feature_matrix(["A"]).empty


# ── windowed feature reads ──────────────────────────────────────────────────


def test_the_recent_matrix_returns_only_the_requested_observations(
    features: MacroFeatureStore,
) -> None:
    """The homepage strip needs a level and its change, not the whole series."""
    dates = [f"2024-01-{day:02d}" for day in range(1, 21)]
    features.upsert_features(_features("UST_2S10S", dates, [float(i) for i in range(20)]))

    matrix = features.get_recent_feature_matrix(["UST_2S10S"], sessions=2)

    assert len(matrix) == 2
    assert matrix["UST_2S10S"].tolist() == [18.0, 19.0]


def test_the_recent_matrix_is_ordered_oldest_first(features: MacroFeatureStore) -> None:
    features.upsert_features(
        _features("A", ["2024-01-01", "2024-01-02", "2024-01-03"], [1.0, 2.0, 3.0])
    )

    matrix = features.get_recent_feature_matrix(["A"], sessions=3)

    assert list(matrix.index) == sorted(matrix.index)


def test_each_feature_is_windowed_on_its_own_calendar(features: MacroFeatureStore) -> None:
    """Monthly and daily features do not share dates; the result is sparse by design."""
    features.upsert_features(_features("DAILY", ["2024-01-01", "2024-01-02"], [1.0, 2.0]))
    features.upsert_features(_features("MONTHLY", ["2023-12-01"], [9.0]))

    matrix = features.get_recent_feature_matrix(["DAILY", "MONTHLY"], sessions=2)

    assert matrix["DAILY"].dropna().tolist() == [1.0, 2.0]
    assert matrix["MONTHLY"].dropna().tolist() == [9.0]


def test_the_recent_matrix_matches_the_tail_of_the_full_matrix(
    features: MacroFeatureStore,
) -> None:
    dates = [f"2024-01-{day:02d}" for day in range(1, 11)]
    features.upsert_features(_features("A", dates, [float(i) for i in range(10)]))

    windowed = features.get_recent_feature_matrix(["A"], sessions=3)["A"]
    full = features.get_feature_matrix(["A"])["A"].tail(3)

    assert windowed.tolist() == full.tolist()


@pytest.mark.parametrize(("names", "sessions"), [([], 2), (["A"], 0)])
def test_a_degenerate_recent_request_is_empty(
    features: MacroFeatureStore, names: list[str], sessions: int
) -> None:
    features.upsert_features(_features("A", ["2024-01-01"], [1.0]))

    assert features.get_recent_feature_matrix(names, sessions=sessions).empty
