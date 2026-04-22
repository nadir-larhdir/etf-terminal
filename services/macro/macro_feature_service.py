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

    def _clean_series(self, series: pd.Series | None) -> pd.Series:
        if series is None:
            return pd.Series(dtype=float)
        return series.dropna().sort_index()

    def _aligned_difference(self, left: pd.Series | None, right: pd.Series | None) -> pd.Series:
        left_clean = self._clean_series(left).rename("left")
        right_clean = self._clean_series(right).rename("right")
        if left_clean.empty or right_clean.empty:
            return pd.Series(dtype=float)
        frame = pd.concat([left_clean, right_clean], axis=1, join="inner").dropna()
        if frame.empty:
            return pd.Series(dtype=float)
        return frame["left"] - frame["right"]

    def _repair_isolated_internal_gaps(
        self,
        series: pd.Series | None,
        *,
        reference_index: pd.Index | None = None,
        max_gap: int = 1,
    ) -> pd.Series:
        clean = self._clean_series(series)
        if clean.empty:
            return clean
        if reference_index is not None:
            clean = clean.reindex(pd.Index(reference_index).sort_values())
        return clean.interpolate(method="time", limit=max_gap, limit_area="inside")

    def build_feature_matrix(self, start_date: str | None = None) -> pd.DataFrame:
        raw = self.macro_store.get_series_matrix(REQUIRED_SERIES, start_date=start_date)
        if raw.empty:
            return pd.DataFrame()

        raw = raw.sort_index()
        feature_map: dict[str, pd.Series] = {}

        dgs3mo = self._clean_series(raw.get("DGS3MO"))
        dgs6mo = self._clean_series(raw.get("DGS6MO"))
        dgs1 = self._clean_series(raw.get("DGS1"))
        dgs2 = self._clean_series(raw.get("DGS2"))
        dgs3 = self._clean_series(raw.get("DGS3"))
        dgs5 = self._clean_series(raw.get("DGS5"))
        dgs7 = self._clean_series(raw.get("DGS7"))
        dgs10 = self._clean_series(raw.get("DGS10"))
        dgs20 = self._clean_series(raw.get("DGS20"))
        dgs30 = self._clean_series(raw.get("DGS30"))

        feature_map["UST_3M_LEVEL"] = dgs3mo
        feature_map["UST_6M_LEVEL"] = dgs6mo
        feature_map["UST_1Y_LEVEL"] = dgs1
        feature_map["UST_2Y_LEVEL"] = dgs2
        feature_map["UST_3Y_LEVEL"] = dgs3
        feature_map["UST_5Y_LEVEL"] = dgs5
        feature_map["UST_7Y_LEVEL"] = dgs7
        feature_map["UST_10Y_LEVEL"] = dgs10
        feature_map["UST_20Y_LEVEL"] = dgs20
        feature_map["UST_30Y_LEVEL"] = dgs30

        ust_2s10s = self._aligned_difference(dgs10, dgs2)
        ust_5s30s = self._aligned_difference(dgs30, dgs5)
        ust_3m10y = self._aligned_difference(dgs10, dgs3mo)
        feature_map["UST_2S10S"] = ust_2s10s
        feature_map["UST_5S30S"] = ust_5s30s
        feature_map["UST_3M10Y"] = ust_3m10y
        feature_map["UST_2S10S_CHANGE_20D"] = self._change(ust_2s10s, 20)
        feature_map["UST_5S30S_CHANGE_20D"] = self._change(ust_5s30s, 20)
        feature_map["UST_10Y_Z20"] = self._zscore(dgs10, 20)
        feature_map["UST_2S10S_Z20"] = self._zscore(ust_2s10s, 20)
        feature_map["UST_2S10S_Z60"] = self._zscore(ust_2s10s, 60)
        feature_map["UST_5S30S_Z20"] = self._zscore(ust_5s30s, 20)
        feature_map["UST_10Y_CHANGE_20D"] = self._change(dgs10, 20)
        feature_map["UST_10Y_CHANGE_60D"] = self._change(dgs10, 60)

        cpi = raw.get("CPIAUCSL")
        if cpi is not None:
            feature_map["CPI_YOY"] = self._monthly_feature(cpi, self._year_over_year_change)
            feature_map["CPI_3M_ANN"] = self._monthly_feature(cpi, self._annualized_3m_change)
        t5yie = self._clean_series(raw.get("T5YIE"))
        feature_map["BEI_5Y"] = t5yie
        feature_map["BEI_5Y_CHANGE_20D"] = self._change(t5yie, 20)
        feature_map["BEI_5Y_Z20"] = self._zscore(t5yie, 20)
        feature_map["REAL_RATE_PROXY"] = self._aligned_difference(dgs10, t5yie)

        fedfunds = raw.get("FEDFUNDS")
        if fedfunds is not None:
            fedfunds_monthly = fedfunds.dropna().sort_index()
            feature_map["FEDFUNDS_LEVEL"] = fedfunds_monthly
            feature_map["FEDFUNDS_CHANGE_3M"] = self._change(fedfunds_monthly, 3)
            feature_map["FEDFUNDS_CHANGE_12M"] = self._change(fedfunds_monthly, 12)
            fedfunds_for_10y = fedfunds_monthly.reindex(dgs10.index).ffill()
            fedfunds_for_2y = fedfunds_monthly.reindex(dgs2.index).ffill()
            feature_map["UST10_MINUS_FEDFUNDS"] = dgs10 - fedfunds_for_10y
            feature_map["UST2_MINUS_FEDFUNDS"] = dgs2 - fedfunds_for_2y

        unrate = raw.get("UNRATE")
        if unrate is not None:
            unrate_monthly = unrate.dropna().sort_index()
            feature_map["UNRATE_LEVEL"] = unrate_monthly
            feature_map["UNRATE_3M_CHANGE"] = self._change(unrate_monthly, 3)
            feature_map["UNRATE_12M_CHANGE"] = self._change(unrate_monthly, 12)

        oas_calendar = (
            self._clean_series(raw.get("BAMLC0A0CM")).index
            .union(self._clean_series(raw.get("BAMLH0A0HYM2")).index)
            .union(self._clean_series(raw.get("BAMLC0A4CBBB")).index)
            .union(self._clean_series(raw.get("BAMLH0A2HYB")).index)
            .sort_values()
        )
        ig_oas = self._repair_isolated_internal_gaps(raw.get("BAMLC0A0CM"), reference_index=oas_calendar)
        hy_oas = self._repair_isolated_internal_gaps(raw.get("BAMLH0A0HYM2"), reference_index=oas_calendar)
        bbb_oas = self._repair_isolated_internal_gaps(raw.get("BAMLC0A4CBBB"), reference_index=oas_calendar)
        single_b_oas = self._repair_isolated_internal_gaps(raw.get("BAMLH0A2HYB"), reference_index=oas_calendar)
        hy_minus_ig = hy_oas - ig_oas
        feature_map["IG_OAS_LEVEL"] = ig_oas
        feature_map["HY_OAS_LEVEL"] = hy_oas
        feature_map["BBB_OAS_LEVEL"] = bbb_oas
        feature_map["SINGLE_B_OAS_LEVEL"] = single_b_oas
        feature_map["IG_OAS_CHANGE_5D"] = self._change(ig_oas, 5)
        feature_map["IG_OAS_CHANGE_20D"] = self._change(ig_oas, 20)
        feature_map["HY_OAS_CHANGE_5D"] = self._change(hy_oas, 5)
        feature_map["HY_OAS_CHANGE_20D"] = self._change(hy_oas, 20)
        feature_map["BBB_OAS_CHANGE_20D"] = self._change(bbb_oas, 20)
        feature_map["SINGLE_B_OAS_CHANGE_20D"] = self._change(single_b_oas, 20)
        feature_map["HY_MINUS_IG_OAS"] = hy_minus_ig
        feature_map["HY_MINUS_IG_OAS_CHANGE_20D"] = self._change(hy_minus_ig, 20)
        feature_map["BBB_MINUS_IG_OAS"] = bbb_oas - ig_oas
        feature_map["SINGLE_B_MINUS_HY_OAS"] = single_b_oas - hy_oas
        feature_map["IG_OAS_Z20"] = self._zscore(ig_oas, 20)
        feature_map["IG_OAS_Z60"] = self._zscore(ig_oas, 60)
        feature_map["HY_OAS_Z20"] = self._zscore(hy_oas, 20)
        feature_map["HY_OAS_Z60"] = self._zscore(hy_oas, 60)
        feature_map["HY_MINUS_IG_OAS_Z20"] = self._zscore(hy_minus_ig, 20)

        return pd.concat(feature_map, axis=1).sort_index()

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

        flattened = (
            matrix.reset_index(names="date")
            .melt(id_vars="date", var_name="feature_name", value_name="value")
            .dropna(subset=["value"])
            .reset_index(drop=True)
        )
        flattened["date"] = pd.to_datetime(flattened["date"]).dt.strftime("%Y-%m-%d")
        flattened["category"] = flattened["feature_name"].map(lambda name: FEATURE_METADATA[name][0])
        flattened["sub_category"] = flattened["feature_name"].map(lambda name: FEATURE_METADATA[name][1])
        flattened["source"] = "derived"
        flattened["last_updated_at"] = datetime.utcnow().isoformat()
        return flattened[self.OUTPUT_COLUMNS]

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
            if incremental:
                self.macro_feature_store.delete_features(
                    start_date=feature_rows["date"].min(),
                    end_date=feature_rows["date"].max(),
                )
            else:
                self.macro_feature_store.delete_features()
            self.macro_feature_store.upsert_features(feature_rows)
        return feature_rows
