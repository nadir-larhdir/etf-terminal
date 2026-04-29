from __future__ import annotations

import pandas as pd
import pytest

from services.macro.macro_feature_service import MacroFeatureService


class FakeMacroStore:
    def __init__(self, matrix: pd.DataFrame) -> None:
        self.matrix = matrix

    def get_series_matrix(self, series_ids=None, start_date=None, end_date=None) -> pd.DataFrame:
        frame = self.matrix.copy()
        if start_date is not None:
            frame = frame.loc[frame.index >= pd.Timestamp(start_date)]
        if end_date is not None:
            frame = frame.loc[frame.index <= pd.Timestamp(end_date)]
        if series_ids:
            frame = frame.loc[:, list(series_ids)]
        return frame


class FakeMacroFeatureStore:
    def __init__(self, latest_date: str | None = None) -> None:
        self.latest_date = latest_date
        self.deleted_ranges: list[tuple[str | None, str | None]] = []

    def upsert_features(self, df: pd.DataFrame) -> None:
        self.last_frame = df.copy()

    def get_latest_feature_date(self) -> str | None:
        return self.latest_date

    def delete_features(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        self.deleted_ranges.append((start_date, end_date))


def test_macro_feature_service_builds_credit_oas_features() -> None:
    index = pd.date_range("2024-01-01", periods=80, freq="D")
    raw = pd.DataFrame(
        {
            "DGS3MO": 5.0,
            "DGS6MO": 4.9,
            "DGS1": 4.8,
            "DGS2": 4.6,
            "DGS3": 4.5,
            "DGS5": 4.4,
            "DGS7": 4.3,
            "DGS10": 4.2,
            "DGS20": 4.3,
            "DGS30": 4.4,
            "CPIAUCSL": pd.Series(range(80), index=index) + 300.0,
            "T5YIE": 2.3,
            "FEDFUNDS": 5.25,
            "UNRATE": 4.0,
            "BAMLC0A0CM": pd.Series(range(80), index=index) / 100.0 + 1.0,
            "BAMLH0A0HYM2": pd.Series(range(80), index=index) / 90.0 + 3.0,
            "BAMLC0A4CBBB": pd.Series(range(80), index=index) / 95.0 + 1.5,
            "BAMLH0A2HYB": pd.Series(range(80), index=index) / 85.0 + 4.0,
        },
        index=index,
    )

    service = MacroFeatureService(FakeMacroStore(raw), FakeMacroFeatureStore())
    matrix = service.build_feature_matrix()

    assert "IG_OAS_LEVEL" in matrix.columns
    assert "HY_OAS_LEVEL" in matrix.columns
    assert "HY_MINUS_IG_OAS" in matrix.columns
    assert "IG_OAS_Z20" in matrix.columns
    assert matrix["HY_MINUS_IG_OAS"].dropna().iloc[-1] == (
        matrix["HY_OAS_LEVEL"].dropna().iloc[-1] - matrix["IG_OAS_LEVEL"].dropna().iloc[-1]
    )


def test_macro_feature_service_incremental_persist_limits_output_window() -> None:
    index = pd.date_range("2024-01-01", periods=500, freq="D")
    raw = pd.DataFrame(
        {
            "DGS3MO": 5.0,
            "DGS6MO": 4.9,
            "DGS1": 4.8,
            "DGS2": 4.6,
            "DGS3": 4.5,
            "DGS5": 4.4,
            "DGS7": 4.3,
            "DGS10": 4.2,
            "DGS20": 4.3,
            "DGS30": 4.4,
            "CPIAUCSL": pd.Series(range(500), index=index) + 300.0,
            "T5YIE": 2.3,
            "FEDFUNDS": 5.25,
            "UNRATE": 4.0,
            "BAMLC0A0CM": pd.Series(range(500), index=index) / 100.0 + 1.0,
            "BAMLH0A0HYM2": pd.Series(range(500), index=index) / 90.0 + 3.0,
            "BAMLC0A4CBBB": pd.Series(range(500), index=index) / 95.0 + 1.5,
            "BAMLH0A2HYB": pd.Series(range(500), index=index) / 85.0 + 4.0,
        },
        index=index,
    )

    feature_store = FakeMacroFeatureStore(latest_date="2025-03-15")
    service = MacroFeatureService(FakeMacroStore(raw), feature_store)
    rows = service.persist_features(incremental=True, rebuild_days=30, warmup_days=120)

    assert not rows.empty
    assert rows["date"].min() >= "2025-02-13"
    assert rows["date"].max() <= "2025-05-14"
    assert feature_store.deleted_ranges == [(rows["date"].min(), rows["date"].max())]


def test_macro_feature_service_repairs_isolated_ig_oas_gap() -> None:
    index = pd.date_range("2024-12-20", periods=6, freq="B")
    raw = pd.DataFrame(
        {
            "DGS3MO": 5.0,
            "DGS6MO": 4.9,
            "DGS1": 4.8,
            "DGS2": 4.6,
            "DGS3": 4.5,
            "DGS5": 4.4,
            "DGS7": 4.3,
            "DGS10": 4.2,
            "DGS20": 4.3,
            "DGS30": 4.4,
            "CPIAUCSL": pd.Series([300.0, 301.0, 302.0, 303.0, 304.0, 305.0], index=index),
            "T5YIE": 2.3,
            "FEDFUNDS": 5.25,
            "UNRATE": 4.0,
            "BAMLC0A0CM": pd.Series([0.82, 0.82, None, 0.81, 0.82, 0.82], index=index),
            "BAMLH0A0HYM2": 2.86,
            "BAMLC0A4CBBB": 1.01,
            "BAMLH0A2HYB": 3.80,
        },
        index=index,
    )

    service = MacroFeatureService(FakeMacroStore(raw), FakeMacroFeatureStore())
    matrix = service.build_feature_matrix()

    repaired_value = matrix.loc[pd.Timestamp("2024-12-24"), "IG_OAS_LEVEL"]
    assert repaired_value == pytest.approx(0.815)
    assert matrix.loc[pd.Timestamp("2024-12-24"), "HY_MINUS_IG_OAS"] == pytest.approx(2.86 - 0.815)


def test_macro_feature_service_full_persist_replaces_entire_table() -> None:
    index = pd.date_range("2024-01-01", periods=80, freq="D")
    raw = pd.DataFrame(
        {
            "DGS3MO": 5.0,
            "DGS6MO": 4.9,
            "DGS1": 4.8,
            "DGS2": 4.6,
            "DGS3": 4.5,
            "DGS5": 4.4,
            "DGS7": 4.3,
            "DGS10": 4.2,
            "DGS20": 4.3,
            "DGS30": 4.4,
            "CPIAUCSL": pd.Series(range(80), index=index) + 300.0,
            "T5YIE": 2.3,
            "FEDFUNDS": 5.25,
            "UNRATE": 4.0,
            "BAMLC0A0CM": pd.Series(range(80), index=index) / 100.0 + 1.0,
            "BAMLH0A0HYM2": pd.Series(range(80), index=index) / 90.0 + 3.0,
            "BAMLC0A4CBBB": pd.Series(range(80), index=index) / 95.0 + 1.5,
            "BAMLH0A2HYB": pd.Series(range(80), index=index) / 85.0 + 4.0,
        },
        index=index,
    )

    feature_store = FakeMacroFeatureStore()
    service = MacroFeatureService(FakeMacroStore(raw), feature_store)
    rows = service.persist_features(incremental=False)

    assert not rows.empty
    assert feature_store.deleted_ranges == [(None, None)]


def test_macro_feature_service_uses_dense_series_calendar_for_rolling_features() -> None:
    treasury_index = pd.date_range("2024-01-01", periods=80, freq="B")
    monthly_index = pd.date_range("2024-01-01", periods=6, freq="MS")
    all_index = treasury_index.union(monthly_index).sort_values()

    raw = pd.DataFrame(index=all_index)
    for idx, (column, base_value) in enumerate(
        {
            "DGS3MO": 5.0,
            "DGS6MO": 4.9,
            "DGS1": 4.8,
            "DGS2": 4.6,
            "DGS3": 4.5,
            "DGS5": 4.4,
            "DGS7": 4.3,
            "DGS10": 4.2,
            "DGS20": 4.3,
            "DGS30": 4.4,
            "T5YIE": 2.3,
            "BAMLC0A0CM": 1.0,
            "BAMLH0A0HYM2": 3.0,
            "BAMLC0A4CBBB": 1.5,
            "BAMLH0A2HYB": 4.0,
        }.items()
    ):
        raw[column] = pd.Series(
            base_value
            + (
                pd.Series(range(len(treasury_index)), index=treasury_index) * (0.001 + idx * 0.0001)
            ),
            index=treasury_index,
        ).reindex(all_index)

    raw["CPIAUCSL"] = pd.Series(range(len(monthly_index)), index=monthly_index) + 300.0
    raw["FEDFUNDS"] = pd.Series(5.25, index=monthly_index)
    raw["UNRATE"] = pd.Series(4.0, index=monthly_index)

    service = MacroFeatureService(FakeMacroStore(raw), FakeMacroFeatureStore())
    matrix = service.build_feature_matrix()

    assert matrix["UST_10Y_LEVEL"].dropna().shape[0] == len(treasury_index)
    assert matrix["UST_10Y_CHANGE_20D"].dropna().shape[0] == len(treasury_index) - 20
    assert matrix["UST_10Y_Z20"].dropna().shape[0] == len(treasury_index) - 19
    assert matrix["BEI_5Y_CHANGE_20D"].dropna().shape[0] == len(treasury_index) - 20


def test_macro_feature_service_preserves_monthly_and_oas_calendars() -> None:
    treasury_index = pd.date_range("2024-01-01", periods=80, freq="B")
    monthly_index = pd.date_range("2024-01-01", periods=15, freq="MS")
    oas_index = pd.date_range("2024-01-01", periods=90, freq="B")
    all_index = treasury_index.union(monthly_index).union(oas_index).sort_values()

    raw = pd.DataFrame(index=all_index)
    for column, value in {
        "DGS3MO": 5.0,
        "DGS6MO": 4.9,
        "DGS1": 4.8,
        "DGS2": 4.6,
        "DGS3": 4.5,
        "DGS5": 4.4,
        "DGS7": 4.3,
        "DGS10": 4.2,
        "DGS20": 4.3,
        "DGS30": 4.4,
        "T5YIE": 2.3,
    }.items():
        raw[column] = pd.Series(value, index=treasury_index).reindex(all_index)

    raw["CPIAUCSL"] = pd.Series(range(len(monthly_index)), index=monthly_index) + 300.0
    raw["FEDFUNDS"] = pd.Series(5.25, index=monthly_index)
    raw["UNRATE"] = pd.Series(4.0, index=monthly_index)
    raw["BAMLC0A0CM"] = pd.Series(range(len(oas_index)), index=oas_index) / 100.0 + 1.0
    raw["BAMLH0A0HYM2"] = pd.Series(range(len(oas_index)), index=oas_index) / 90.0 + 3.0
    raw["BAMLC0A4CBBB"] = pd.Series(range(len(oas_index)), index=oas_index) / 95.0 + 1.5
    raw["BAMLH0A2HYB"] = pd.Series(range(len(oas_index)), index=oas_index) / 85.0 + 4.0

    service = MacroFeatureService(FakeMacroStore(raw), FakeMacroFeatureStore())
    matrix = service.build_feature_matrix()

    assert matrix["FEDFUNDS_LEVEL"].dropna().shape[0] == len(monthly_index)
    assert matrix["FEDFUNDS_CHANGE_3M"].dropna().shape[0] == len(monthly_index) - 3
    assert matrix["CPI_YOY"].dropna().shape[0] == len(monthly_index) - 12
    assert matrix["HY_MINUS_IG_OAS"].dropna().shape[0] == len(oas_index)
    assert matrix["HY_MINUS_IG_OAS_Z20"].dropna().shape[0] == len(oas_index) - 19
