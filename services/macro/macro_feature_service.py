from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


FEATURE_METADATA = {
    "UST_3M_LEVEL": ("Rates", "Rates Level"),
    "UST_6M_LEVEL": ("Rates", "Rates Level"),
    "UST_1Y_LEVEL": ("Rates", "Rates Level"),
    "UST_2Y_LEVEL": ("Rates", "Rates Level"),
    "UST_3Y_LEVEL": ("Rates", "Rates Level"),
    "UST_5Y_LEVEL": ("Rates", "Rates Level"),
    "UST_7Y_LEVEL": ("Rates", "Rates Level"),
    "UST_10Y_LEVEL": ("Rates", "Rates Level"),
    "UST_20Y_LEVEL": ("Rates", "Rates Level"),
    "UST_30Y_LEVEL": ("Rates", "Rates Level"),
    "UST_2S10S": ("Rates", "Curve"),
    "UST_5S30S": ("Rates", "Curve"),
    "UST_3M10Y": ("Rates", "Curve"),
    "UST_2S10S_Z20": ("Rates", "Curve"),
    "UST_2S10S_Z60": ("Rates", "Curve"),
    "UST_5S30S_Z20": ("Rates", "Curve"),
    "UST_10Y_CHANGE_20D": ("Rates", "Curve"),
    "UST_10Y_CHANGE_60D": ("Rates", "Curve"),
    "CPI_YOY": ("Inflation", "Inflation Trend"),
    "CPI_3M_ANN": ("Inflation", "Inflation Trend"),
    "BEI_5Y": ("Inflation", "Breakevens"),
    "BEI_5Y_CHANGE_20D": ("Inflation", "Breakevens"),
    "BEI_5Y_Z20": ("Inflation", "Breakevens"),
    "REAL_RATE_PROXY": ("Inflation", "Real Rates"),
    "FEDFUNDS_LEVEL": ("Policy", "Policy Level"),
    "UST10_MINUS_FEDFUNDS": ("Policy", "Policy Spread"),
    "UST2_MINUS_FEDFUNDS": ("Policy", "Policy Spread"),
    "FEDFUNDS_CHANGE_3M": ("Policy", "Policy Change"),
    "FEDFUNDS_CHANGE_12M": ("Policy", "Policy Change"),
    "UNRATE_LEVEL": ("Growth", "Labor"),
    "UNRATE_3M_CHANGE": ("Growth", "Labor"),
    "UNRATE_12M_CHANGE": ("Growth", "Labor"),
}

REQUIRED_SERIES = [
    "DGS3MO",
    "DGS6MO",
    "DGS1",
    "DGS2",
    "DGS3",
    "DGS5",
    "DGS7",
    "DGS10",
    "DGS20",
    "DGS30",
    "CPIAUCSL",
    "T5YIE",
    "FEDFUNDS",
    "UNRATE",
]


class MacroFeatureService:
    """Build derived macro features from raw FRED observations."""

    def __init__(self, macro_repository, macro_feature_repository):
        self.macro_repository = macro_repository
        self.macro_feature_repository = macro_feature_repository

    def _zscore(self, series: pd.Series, window: int) -> pd.Series:
        rolling_mean = series.rolling(window).mean()
        rolling_std = series.rolling(window).std(ddof=0)
        return (series - rolling_mean) / rolling_std.replace(0, np.nan)

    def _change(self, series: pd.Series, periods: int) -> pd.Series:
        return series - series.shift(periods)

    def _annualized_3m_change(self, series: pd.Series) -> pd.Series:
        return ((series / series.shift(3)) ** 4 - 1.0) * 100.0

    def _year_over_year_change(self, series: pd.Series) -> pd.Series:
        return ((series / series.shift(12)) - 1.0) * 100.0

    def _monthly_feature(self, series: pd.Series, transform) -> pd.Series:
        clean = series.dropna().sort_index()
        if clean.empty:
            return clean
        return transform(clean)

    def build_feature_matrix(self) -> pd.DataFrame:
        raw = self.macro_repository.get_series_matrix(REQUIRED_SERIES)
        if raw.empty:
            return pd.DataFrame()

        raw = raw.sort_index()
        features = pd.DataFrame(index=raw.index)

        features["UST_3M_LEVEL"] = raw.get("DGS3MO")
        features["UST_6M_LEVEL"] = raw.get("DGS6MO")
        features["UST_1Y_LEVEL"] = raw.get("DGS1")
        features["UST_2Y_LEVEL"] = raw.get("DGS2")
        features["UST_3Y_LEVEL"] = raw.get("DGS3")
        features["UST_5Y_LEVEL"] = raw.get("DGS5")
        features["UST_7Y_LEVEL"] = raw.get("DGS7")
        features["UST_10Y_LEVEL"] = raw.get("DGS10")
        features["UST_20Y_LEVEL"] = raw.get("DGS20")
        features["UST_30Y_LEVEL"] = raw.get("DGS30")

        features["UST_2S10S"] = raw.get("DGS10") - raw.get("DGS2")
        features["UST_5S30S"] = raw.get("DGS30") - raw.get("DGS5")
        features["UST_3M10Y"] = raw.get("DGS10") - raw.get("DGS3MO")
        features["UST_2S10S_Z20"] = self._zscore(features["UST_2S10S"], 20)
        features["UST_2S10S_Z60"] = self._zscore(features["UST_2S10S"], 60)
        features["UST_5S30S_Z20"] = self._zscore(features["UST_5S30S"], 20)
        features["UST_10Y_CHANGE_20D"] = self._change(raw.get("DGS10"), 20)
        features["UST_10Y_CHANGE_60D"] = self._change(raw.get("DGS10"), 60)

        cpi = raw.get("CPIAUCSL")
        if cpi is not None:
            features["CPI_YOY"] = self._monthly_feature(cpi, self._year_over_year_change)
            features["CPI_3M_ANN"] = self._monthly_feature(cpi, self._annualized_3m_change)
        features["BEI_5Y"] = raw.get("T5YIE")
        features["BEI_5Y_CHANGE_20D"] = self._change(raw.get("T5YIE"), 20)
        features["BEI_5Y_Z20"] = self._zscore(raw.get("T5YIE"), 20)
        features["REAL_RATE_PROXY"] = raw.get("DGS10") - raw.get("T5YIE")

        fedfunds = raw.get("FEDFUNDS")
        if fedfunds is not None:
            fedfunds_monthly = fedfunds.dropna().sort_index()
            features["FEDFUNDS_LEVEL"] = fedfunds_monthly
            features["FEDFUNDS_CHANGE_3M"] = self._change(fedfunds_monthly, 3)
            features["FEDFUNDS_CHANGE_12M"] = self._change(fedfunds_monthly, 12)
            fedfunds_daily = fedfunds_monthly.reindex(raw.index).ffill()
            features["UST10_MINUS_FEDFUNDS"] = raw.get("DGS10") - fedfunds_daily
            features["UST2_MINUS_FEDFUNDS"] = raw.get("DGS2") - fedfunds_daily

        unrate = raw.get("UNRATE")
        if unrate is not None:
            unrate_monthly = unrate.dropna().sort_index()
            features["UNRATE_LEVEL"] = unrate_monthly
            features["UNRATE_3M_CHANGE"] = self._change(unrate_monthly, 3)
            features["UNRATE_12M_CHANGE"] = self._change(unrate_monthly, 12)

        return features.sort_index()

    def build_feature_rows(self) -> pd.DataFrame:
        matrix = self.build_feature_matrix()
        if matrix.empty:
            return pd.DataFrame(
                columns=[
                    "feature_name",
                    "date",
                    "value",
                    "category",
                    "sub_category",
                    "source",
                    "last_updated_at",
                ]
            )

        stacked = matrix.stack(dropna=True).reset_index()
        stacked.columns = ["date", "feature_name", "value"]
        stacked["date"] = pd.to_datetime(stacked["date"]).dt.strftime("%Y-%m-%d")
        stacked["category"] = stacked["feature_name"].map(lambda name: FEATURE_METADATA[name][0])
        stacked["sub_category"] = stacked["feature_name"].map(lambda name: FEATURE_METADATA[name][1])
        stacked["source"] = "derived"
        stacked["last_updated_at"] = datetime.utcnow().isoformat()
        return stacked[
            [
                "feature_name",
                "date",
                "value",
                "category",
                "sub_category",
                "source",
                "last_updated_at",
            ]
        ]

    def persist_features(self) -> pd.DataFrame:
        feature_rows = self.build_feature_rows()
        if not feature_rows.empty:
            self.macro_feature_repository.upsert_features(feature_rows)
        return feature_rows
