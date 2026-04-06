from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from models.security import Security
from services.analytics.result_models import (
    RateRiskEstimate,
    SecurityAnalyticsSnapshot,
    SpreadRiskEstimate,
)


class FixedIncomeAnalyticsService:
    """Estimate rate and spread risk for fixed-income ETFs using stored market data."""

    RATE_SERIES = ("DGS2", "DGS5", "DGS10", "DGS30")

    def __init__(self, price_store, macro_store, duration_selector) -> None:
        self.price_store = price_store
        self.macro_store = macro_store
        self.duration_selector = duration_selector

    def analyze_security(self, security: Security) -> SecurityAnalyticsSnapshot:
        returns = security.log_returns()
        latest_price = security.last_price()
        if returns.empty or latest_price is None:
            return self._empty_snapshot(security, "Insufficient ETF price history.")

        start_date = (returns.index.max() - pd.Timedelta(days=260)).date().isoformat()
        rates = self.macro_store.get_series_matrix(list(self.RATE_SERIES), start_date=start_date)
        if rates.empty:
            return self._empty_snapshot(security, "Treasury rate history is unavailable.")

        missing = [series_id for series_id in self.RATE_SERIES if series_id not in rates.columns]
        if missing:
            return self._empty_snapshot(security, f"Missing Treasury series: {', '.join(missing)}.")

        rate_changes_bps = rates.loc[:, list(self.RATE_SERIES)].astype(float).diff().mul(100.0).dropna()
        aligned = returns.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
        if len(aligned) < 20:
            return self._empty_snapshot(security, "Not enough overlapping ETF and Treasury observations.")

        curve_60d = self._regress_curve_duration(aligned.tail(60), 60)
        curve_120d = self._regress_curve_duration(aligned.tail(120), 120)
        rough_duration = self._ewma_blend([curve_120d["estimated_duration"], curve_60d["estimated_duration"]])
        selection = self.duration_selector.select_for_security(security, rough_duration=rough_duration)

        headline_60d = curve_60d
        headline_120d = curve_120d
        spread_estimate: SpreadRiskEstimate | None = None

        if selection.duration_model_type == "treasury_etf_benchmark_regression" and selection.treasury_benchmark_symbol:
            benchmark_duration = self._benchmark_duration_proxy(selection.treasury_benchmark_symbol, start_date)
            benchmark_returns = self._benchmark_returns(selection.treasury_benchmark_symbol, start_date)
            if benchmark_duration is not None and not benchmark_returns.empty:
                benchmark_frame = aligned.join(benchmark_returns.rename("benchmark_return"), how="inner")
                if selection.spread_proxy_series_id:
                    spread_estimate, headline_60d, headline_120d = self._credit_benchmark_models(
                        benchmark_frame,
                        selection.spread_proxy_series_id,
                        benchmark_duration,
                        latest_price,
                        start_date,
                    )
                    if headline_60d["estimated_duration"] is None or headline_120d["estimated_duration"] is None:
                        headline_60d = self._regress_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
                        headline_120d = self._regress_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)
                elif len(benchmark_frame) >= 20:
                    headline_60d = self._regress_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
                    headline_120d = self._regress_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)
        elif selection.spread_proxy_series_id:
            spread_estimate = self._curve_spread_model(aligned, selection.spread_proxy_series_id, latest_price, start_date)

        estimated_duration = self._ewma_blend([headline_120d["estimated_duration"], headline_60d["estimated_duration"]])
        rate_model_r2 = self._ewma_blend([headline_120d["regression_r2"], headline_60d["regression_r2"]])
        rate_risk = RateRiskEstimate(
            estimated_duration=estimated_duration,
            dv01_per_share=None if estimated_duration is None else estimated_duration * latest_price * 0.0001,
            ir01_per_share=None if estimated_duration is None else estimated_duration * latest_price * 0.0001,
            regression_r2=rate_model_r2,
            benchmark_used=selection.treasury_benchmark_symbol,
            rate_proxy_used=selection.rate_proxy_description,
            lookback_days_used=120 if headline_120d["estimated_duration"] is not None else headline_60d["lookback_days_used"],
            observations_used=headline_120d["observations_used"] or headline_60d["observations_used"],
        )
        reason = (headline_120d["reason"] or headline_60d["reason"] or "").strip() or None
        if selection.asset_bucket == "High Yield":
            extra = "High-yield duration is model-based and more sensitive to benchmark and spread specification than Treasury and IG estimates."
            reason = f"{reason} {extra}".strip() if reason else extra

        return SecurityAnalyticsSnapshot(
            ticker=security.ticker,
            asset_bucket=selection.asset_bucket,
            model_type_used=selection.duration_model_type,
            confidence_level=selection.confidence_level,
            notes=selection.notes,
            reason=reason,
            rate_risk=rate_risk,
            spread_risk=spread_estimate,
        )

    def _credit_benchmark_models(
        self,
        benchmark_frame: pd.DataFrame,
        spread_proxy_series_id: str,
        benchmark_duration: float,
        latest_price: float,
        start_date: str,
    ) -> tuple[SpreadRiskEstimate | None, dict[str, Any], dict[str, Any]]:
        spread_matrix = self.macro_store.get_series_matrix([spread_proxy_series_id], start_date=start_date)
        if spread_matrix.empty or spread_proxy_series_id not in spread_matrix.columns:
            return None, self._empty_model("Spread history unavailable."), self._empty_model("Spread history unavailable.")

        spread_change = (
            spread_matrix[spread_proxy_series_id].astype(float).diff().mul(100.0).dropna().rename("spread_change_bps")
        )
        benchmark_frame = benchmark_frame.join(spread_change, how="inner")
        if len(benchmark_frame) < 20:
            return None, self._empty_model("Not enough observations for benchmark and spread regression."), self._empty_model("Not enough observations for benchmark and spread regression.")

        model_60d = self._regress_credit_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
        model_120d = self._regress_credit_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)
        spread_beta = self._ewma_blend([model_120d["credit_beta"], model_60d["credit_beta"]])
        spread_r2 = self._ewma_blend([model_120d["regression_r2"], model_60d["regression_r2"]])
        spread_estimate = SpreadRiskEstimate(
            beta_per_bp=spread_beta,
            dv01_proxy_per_share=None if spread_beta is None else abs(spread_beta) * latest_price,
            regression_r2=spread_r2,
            proxy_used=spread_proxy_series_id,
        )
        return spread_estimate, model_60d, model_120d

    def _curve_spread_model(
        self,
        aligned: pd.DataFrame,
        spread_proxy_series_id: str,
        latest_price: float,
        start_date: str,
    ) -> SpreadRiskEstimate | None:
        spread_matrix = self.macro_store.get_series_matrix([spread_proxy_series_id], start_date=start_date)
        if spread_matrix.empty or spread_proxy_series_id not in spread_matrix.columns:
            return None

        spread_change = spread_matrix[spread_proxy_series_id].astype(float).diff().mul(100.0).dropna().rename("spread_change_bps")
        spread_frame = aligned.join(spread_change, how="inner")
        if len(spread_frame) < 20:
            return None

        spread_columns = [*self.RATE_SERIES, "spread_change_bps"]
        spread_60d = self._regress_duration(spread_frame.tail(60), 60, spread_columns)
        spread_120d = self._regress_duration(spread_frame.tail(120), 120, spread_columns)
        beta = self._ewma_blend([spread_120d["credit_beta"], spread_60d["credit_beta"]])
        return SpreadRiskEstimate(
            beta_per_bp=beta,
            dv01_proxy_per_share=None if beta is None else abs(beta) * latest_price,
            regression_r2=self._ewma_blend([spread_120d["regression_r2"], spread_60d["regression_r2"]]),
            proxy_used=spread_proxy_series_id,
        )

    def _benchmark_duration_proxy(self, benchmark_ticker: str, start_date: str) -> float | None:
        benchmark_history = self.price_store.get_ticker_price_history(benchmark_ticker, start_date=start_date)
        if benchmark_history.empty:
            return None

        benchmark = Security(benchmark_ticker, history=benchmark_history)
        returns = benchmark.log_returns()
        if returns.empty:
            return None

        rates = self.macro_store.get_series_matrix(list(self.RATE_SERIES), start_date=start_date)
        if rates.empty or any(series_id not in rates.columns for series_id in self.RATE_SERIES):
            return None

        rate_changes_bps = rates.loc[:, list(self.RATE_SERIES)].astype(float).diff().mul(100.0).dropna()
        aligned = returns.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
        if len(aligned) < 20:
            return None

        model_60d = self._regress_curve_duration(aligned.tail(60), 60)
        model_120d = self._regress_curve_duration(aligned.tail(120), 120)
        return self._ewma_blend([model_120d["estimated_duration"], model_60d["estimated_duration"]])

    def _benchmark_returns(self, benchmark_ticker: str, start_date: str) -> pd.Series:
        benchmark_history = self.price_store.get_ticker_price_history(benchmark_ticker, start_date=start_date)
        if benchmark_history.empty:
            return pd.Series(dtype=float)
        column = "adj_close" if "adj_close" in benchmark_history.columns else "close"
        prices = benchmark_history[column].replace(0, np.nan).dropna()
        return np.log(prices).diff().dropna()

    def _regress_curve_duration(self, frame: pd.DataFrame, lookback_days: int) -> dict[str, Any]:
        return self._regress_duration(frame, lookback_days, list(self.RATE_SERIES))

    def _regress_benchmark_duration(self, frame: pd.DataFrame, lookback_days: int, benchmark_duration: float) -> dict[str, Any]:
        return self._regress_with_controls(
            frame,
            lookback_days,
            ["benchmark_return"],
            benchmark_duration=benchmark_duration,
        )

    def _regress_credit_benchmark_duration(self, frame: pd.DataFrame, lookback_days: int, benchmark_duration: float) -> dict[str, Any]:
        return self._regress_with_controls(
            frame,
            lookback_days,
            ["benchmark_return", "spread_change_bps"],
            benchmark_duration=benchmark_duration,
        )

    def _regress_with_controls(
        self,
        frame: pd.DataFrame,
        lookback_days: int,
        factor_columns: list[str],
        benchmark_duration: float,
    ) -> dict[str, Any]:
        minimum = max(20, lookback_days // 3)
        if len(frame) < minimum:
            return self._empty_model("Not enough observations for benchmark regression.", len(frame), lookback_days)

        filtered = self._filter_outliers(frame)
        if len(filtered) < minimum:
            return self._empty_model("Not enough observations after outlier filtering.", len(filtered), len(filtered))

        y = filtered["etf_return"].to_numpy(dtype=float)
        x = filtered.loc[:, factor_columns].to_numpy(dtype=float)
        weights = self._ewma_weights(len(filtered), lookback_days)
        design = np.column_stack([np.ones(len(filtered)), x])
        coeffs, r2 = self._weighted_fit(design, y, weights)
        beta_map = dict(zip(factor_columns, coeffs[1:], strict=False))
        return {
            "estimated_duration": float(beta_map["benchmark_return"] * benchmark_duration),
            "regression_r2": r2,
            "lookback_days_used": lookback_days,
            "observations_used": len(filtered),
            "credit_beta": self._factor_beta(beta_map),
            "reason": None,
        }

    def _regress_duration(
        self,
        frame: pd.DataFrame,
        lookback_days: int,
        factor_columns: list[str],
        orthogonalize_credit: bool = False,
    ) -> dict[str, Any]:
        minimum = max(20, lookback_days // 3)
        if len(frame) < minimum:
            return self._empty_model("Not enough observations for regression.", len(frame), lookback_days)

        filtered = self._filter_outliers(frame)
        if len(filtered) < minimum:
            return self._empty_model("Not enough observations after outlier filtering.", len(filtered), len(filtered))

        filtered = filtered.copy()
        if orthogonalize_credit and "credit_proxy_return" in factor_columns:
            filtered.loc[:, "credit_proxy_return"] = self._orthogonalize_credit_factor(filtered)

        y = filtered["etf_return"].to_numpy(dtype=float)
        x = filtered.loc[:, factor_columns].to_numpy(dtype=float)
        weights = self._ewma_weights(len(filtered), lookback_days)
        design = np.column_stack([np.ones(len(filtered)), x])
        coeffs, r2 = self._weighted_fit(design, y, weights)
        beta_map = dict(zip(factor_columns, coeffs[1:], strict=False))
        rate_beta_sum = sum(float(beta_map.get(series_id, 0.0)) for series_id in self.RATE_SERIES)
        return {
            "estimated_duration": float(-(rate_beta_sum * 10000.0)),
            "regression_r2": r2,
            "lookback_days_used": lookback_days,
            "observations_used": len(filtered),
            "credit_beta": self._factor_beta(beta_map),
            "reason": None,
        }

    def _weighted_fit(self, design: np.ndarray, y: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, float | None]:
        sqrt_w = np.sqrt(weights)
        coeffs = np.linalg.lstsq(design * sqrt_w[:, None], y * sqrt_w, rcond=None)[0]
        fitted = design @ coeffs
        weighted_mean = float(np.average(y, weights=weights))
        total = float(np.sum(weights * (y - weighted_mean) ** 2))
        residual = float(np.sum(weights * (y - fitted) ** 2))
        r2 = None if total <= 0 else max(0.0, 1.0 - residual / total)
        return coeffs, None if r2 is None else float(r2)

    def _empty_snapshot(self, security: Security, reason: str) -> SecurityAnalyticsSnapshot:
        selection = self.duration_selector.select_for_security(security, rough_duration=None)
        return SecurityAnalyticsSnapshot(
            ticker=security.ticker,
            asset_bucket=selection.asset_bucket,
            model_type_used=selection.duration_model_type,
            confidence_level=selection.confidence_level,
            notes=selection.notes,
            reason=reason,
            rate_risk=RateRiskEstimate(
                estimated_duration=None,
                dv01_per_share=None,
                ir01_per_share=None,
                regression_r2=None,
                benchmark_used=selection.treasury_benchmark_symbol,
                rate_proxy_used=selection.rate_proxy_description,
                lookback_days_used=None,
                observations_used=None,
            ),
            spread_risk=SpreadRiskEstimate(
                beta_per_bp=None,
                dv01_proxy_per_share=None,
                regression_r2=None,
                proxy_used=selection.spread_proxy_series_id,
            )
            if selection.spread_proxy_series_id
            else None,
        )

    def _empty_model(
        self,
        reason: str,
        observations_used: int | None = None,
        lookback_days_used: int | None = None,
    ) -> dict[str, Any]:
        return {
            "estimated_duration": None,
            "regression_r2": None,
            "lookback_days_used": lookback_days_used,
            "observations_used": observations_used,
            "credit_beta": None,
            "reason": reason,
        }

    def _ewma_blend(self, values: list[float | None], alpha: float = 0.65) -> float | None:
        valid = [value for value in values if value is not None and not pd.isna(value)]
        if not valid:
            return None
        return float(pd.Series(valid, dtype=float).ewm(alpha=alpha, adjust=False).mean().iloc[-1])

    def _ewma_weights(self, length: int, lookback_days: int) -> np.ndarray:
        half_life = max(10.0, lookback_days / 3.0)
        ages = np.arange(length - 1, -1, -1, dtype=float)
        return np.power(0.5, ages / half_life)

    def _filter_outliers(self, frame: pd.DataFrame) -> pd.DataFrame:
        lower = frame["etf_return"].quantile(0.01)
        upper = frame["etf_return"].quantile(0.99)
        return frame.loc[frame["etf_return"].between(lower, upper)].copy()

    def _orthogonalize_credit_factor(self, frame: pd.DataFrame) -> np.ndarray:
        y = frame["credit_proxy_return"].to_numpy(dtype=float)
        x = frame.loc[:, list(self.RATE_SERIES)].to_numpy(dtype=float)
        design = np.column_stack([np.ones(len(frame)), x])
        coeffs = np.linalg.lstsq(design, y, rcond=None)[0]
        return y - (design @ coeffs)

    def _factor_beta(self, beta_map: dict[str, float]) -> float | None:
        for factor_name in ("spread_change_bps", "credit_proxy_return"):
            if factor_name in beta_map:
                return float(beta_map[factor_name])
        return None
