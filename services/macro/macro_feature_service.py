from __future__ import annotations

from datetime import datetime, timedelta

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
    "UST_2S10S_CHANGE_20D": ("Rates", "Curve"),
    "UST_5S30S_CHANGE_20D": ("Rates", "Curve"),
    "UST_10Y_Z20": ("Rates", "Rates Level"),
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
    "IG_OAS_LEVEL": ("Credit", "OAS Level"),
    "HY_OAS_LEVEL": ("Credit", "OAS Level"),
    "BBB_OAS_LEVEL": ("Credit", "OAS Level"),
    "SINGLE_B_OAS_LEVEL": ("Credit", "OAS Level"),
    "IG_OAS_CHANGE_5D": ("Credit", "OAS Change"),
    "IG_OAS_CHANGE_20D": ("Credit", "OAS Change"),
    "HY_OAS_CHANGE_5D": ("Credit", "OAS Change"),
    "HY_OAS_CHANGE_20D": ("Credit", "OAS Change"),
    "BBB_OAS_CHANGE_20D": ("Credit", "OAS Change"),
    "SINGLE_B_OAS_CHANGE_20D": ("Credit", "OAS Change"),
    "HY_MINUS_IG_OAS_CHANGE_20D": ("Credit", "Spread Curve"),
    "HY_MINUS_IG_OAS": ("Credit", "Spread Curve"),
    "BBB_MINUS_IG_OAS": ("Credit", "Spread Curve"),
    "SINGLE_B_MINUS_HY_OAS": ("Credit", "Spread Curve"),
    "IG_OAS_Z20": ("Credit", "OAS Z-Score"),
    "IG_OAS_Z60": ("Credit", "OAS Z-Score"),
    "HY_OAS_Z20": ("Credit", "OAS Z-Score"),
    "HY_OAS_Z60": ("Credit", "OAS Z-Score"),
    "HY_MINUS_IG_OAS_Z20": ("Credit", "OAS Z-Score"),
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
    "BAMLC0A0CM",
    "BAMLH0A0HYM2",
    "BAMLC0A4CBBB",
    "BAMLH0A2HYB",
]


class MacroFeatureService:
    """Build derived macro features from raw FRED observations."""

    DEFAULT_INCREMENTAL_REBUILD_DAYS = 45
    DEFAULT_WARMUP_DAYS = 450

    OUTPUT_COLUMNS = [
        "feature_name",
        "date",
        "value",
        "category",
        "sub_category",
        "source",
        "last_updated_at",
    ]

    def __init__(self, macro_store, macro_feature_store):
        self.macro_store = macro_store
        self.macro_feature_store = macro_feature_store

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

    def build_feature_matrix(self, start_date: str | None = None) -> pd.DataFrame:
        raw = self.macro_store.get_series_matrix(REQUIRED_SERIES, start_date=start_date)
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
        features["UST_2S10S_CHANGE_20D"] = self._change(features["UST_2S10S"], 20)
        features["UST_5S30S_CHANGE_20D"] = self._change(features["UST_5S30S"], 20)
        features["UST_10Y_Z20"] = self._zscore(raw.get("DGS10"), 20)
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

        ig_oas = raw.get("BAMLC0A0CM")
        hy_oas = raw.get("BAMLH0A0HYM2")
        bbb_oas = raw.get("BAMLC0A4CBBB")
        single_b_oas = raw.get("BAMLH0A2HYB")
        features["IG_OAS_LEVEL"] = ig_oas
        features["HY_OAS_LEVEL"] = hy_oas
        features["BBB_OAS_LEVEL"] = bbb_oas
        features["SINGLE_B_OAS_LEVEL"] = single_b_oas
        features["IG_OAS_CHANGE_5D"] = self._change(ig_oas, 5)
        features["IG_OAS_CHANGE_20D"] = self._change(ig_oas, 20)
        features["HY_OAS_CHANGE_5D"] = self._change(hy_oas, 5)
        features["HY_OAS_CHANGE_20D"] = self._change(hy_oas, 20)
        features["BBB_OAS_CHANGE_20D"] = self._change(bbb_oas, 20)
        features["SINGLE_B_OAS_CHANGE_20D"] = self._change(single_b_oas, 20)
        features["HY_MINUS_IG_OAS"] = hy_oas - ig_oas
        features["HY_MINUS_IG_OAS_CHANGE_20D"] = self._change(features["HY_MINUS_IG_OAS"], 20)
        features["BBB_MINUS_IG_OAS"] = bbb_oas - ig_oas
        features["SINGLE_B_MINUS_HY_OAS"] = single_b_oas - hy_oas
        features["IG_OAS_Z20"] = self._zscore(ig_oas, 20)
        features["IG_OAS_Z60"] = self._zscore(ig_oas, 60)
        features["HY_OAS_Z20"] = self._zscore(hy_oas, 20)
        features["HY_OAS_Z60"] = self._zscore(hy_oas, 60)
        features["HY_MINUS_IG_OAS_Z20"] = self._zscore(features["HY_MINUS_IG_OAS"], 20)

        return features.sort_index()

    def build_feature_rows(
        self,
        *,
        output_start_date: str | None = None,
        source_start_date: str | None = None,
    ) -> pd.DataFrame:
        matrix = self.build_feature_matrix(start_date=source_start_date)
        if matrix.empty:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        if output_start_date is not None:
            matrix = matrix.loc[matrix.index >= pd.Timestamp(output_start_date)].copy()
            if matrix.empty:
                return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        stacked = matrix.stack(dropna=True).reset_index()
        stacked.columns = ["date", "feature_name", "value"]
        stacked["date"] = pd.to_datetime(stacked["date"]).dt.strftime("%Y-%m-%d")
        stacked["category"] = stacked["feature_name"].map(lambda name: FEATURE_METADATA[name][0])
        stacked["sub_category"] = stacked["feature_name"].map(lambda name: FEATURE_METADATA[name][1])
        stacked["source"] = "derived"
        stacked["last_updated_at"] = datetime.utcnow().isoformat()
        return stacked[self.OUTPUT_COLUMNS]

    def incremental_start_dates(
        self,
        *,
        rebuild_days: int = DEFAULT_INCREMENTAL_REBUILD_DAYS,
        warmup_days: int = DEFAULT_WARMUP_DAYS,
    ) -> tuple[str | None, str | None]:
        latest_feature_date = self.macro_feature_store.get_latest_feature_date()
        if latest_feature_date is None:
            return None, None

        output_start = pd.Timestamp(latest_feature_date) - timedelta(days=rebuild_days)
        source_start = output_start - timedelta(days=warmup_days)
        return output_start.date().isoformat(), source_start.date().isoformat()

    def persist_features(
        self,
        *,
        incremental: bool = False,
        rebuild_days: int = DEFAULT_INCREMENTAL_REBUILD_DAYS,
        warmup_days: int = DEFAULT_WARMUP_DAYS,
    ) -> pd.DataFrame:
        output_start_date = None
        source_start_date = None
        if incremental:
            output_start_date, source_start_date = self.incremental_start_dates(
                rebuild_days=rebuild_days,
                warmup_days=warmup_days,
            )

        feature_rows = self.build_feature_rows(
            output_start_date=output_start_date,
            source_start_date=source_start_date,
        )
        if not feature_rows.empty:
            self.macro_feature_store.upsert_features(feature_rows)
        return feature_rows
