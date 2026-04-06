from __future__ import annotations

import pandas as pd

from services.macro.macro_feature_service import MacroFeatureService


class FakeMacroStore:
    def __init__(self, matrix: pd.DataFrame) -> None:
        self.matrix = matrix

    def get_series_matrix(self, series_ids=None, start_date=None, end_date=None) -> pd.DataFrame:
        frame = self.matrix.copy()
        if series_ids:
            frame = frame.loc[:, list(series_ids)]
        return frame


class FakeMacroFeatureStore:
    def upsert_features(self, df: pd.DataFrame) -> None:
        self.last_frame = df.copy()


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
