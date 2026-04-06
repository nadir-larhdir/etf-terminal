from __future__ import annotations

import pandas as pd

from fixed_income.analytics.factor_data import benchmark_returns, spread_changes_bps, treasury_rate_changes_bps
from fixed_income.analytics.rate_models import ewma_blend, regress_benchmark_duration, regress_duration
from fixed_income.analytics.result_models import RateRiskEstimate, SecurityAnalyticsSnapshot, SpreadRiskEstimate
from fixed_income.analytics.spread_models import regress_credit_benchmark_duration
from fixed_income.config.model_settings import RATE_FACTOR_LABEL, RATE_SERIES
from fixed_income.instruments.security import Security


class FixedIncomeAnalyticsService:
    """Estimate rate and spread risk for fixed-income instruments from stored data."""

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
        rate_changes_bps = treasury_rate_changes_bps(self.macro_store, start_date=start_date)
        if rate_changes_bps.empty:
            return self._empty_snapshot(security, "Treasury rate history is unavailable.")

        missing = [series_id for series_id in RATE_SERIES if series_id not in rate_changes_bps.columns]
        if missing:
            return self._empty_snapshot(security, f"Missing Treasury series: {', '.join(missing)}.")

        aligned = returns.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
        if len(aligned) < 20:
            return self._empty_snapshot(security, "Not enough overlapping ETF and Treasury observations.")

        curve_60d = regress_duration(aligned.tail(60), 60, list(RATE_SERIES))
        curve_120d = regress_duration(aligned.tail(120), 120, list(RATE_SERIES))
        rough_duration = ewma_blend([curve_120d["estimated_duration"], curve_60d["estimated_duration"]])
        selection = self.duration_selector.select_for_security(security, rough_duration=rough_duration)

        headline_60d = curve_60d
        headline_120d = curve_120d
        spread_estimate: SpreadRiskEstimate | None = None

        if selection.duration_model_type == "treasury_etf_benchmark_regression" and selection.treasury_benchmark_symbol:
            benchmark_duration = self._benchmark_duration_proxy(selection.treasury_benchmark_symbol, start_date)
            benchmark_series = benchmark_returns(self.price_store, selection.treasury_benchmark_symbol, start_date=start_date)
            if benchmark_duration is not None and not benchmark_series.empty:
                benchmark_frame = aligned.join(benchmark_series.rename("benchmark_return"), how="inner")
                if selection.spread_proxy_series_id:
                    spread_series = spread_changes_bps(self.macro_store, selection.spread_proxy_series_id, start_date=start_date)
                    if not spread_series.empty:
                        benchmark_frame = benchmark_frame.join(spread_series, how="inner")
                    if len(benchmark_frame) >= 20 and "spread_change_bps" in benchmark_frame.columns:
                        headline_60d = regress_credit_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
                        headline_120d = regress_credit_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)
                        spread_beta = ewma_blend([headline_120d["credit_beta"], headline_60d["credit_beta"]])
                        spread_estimate = SpreadRiskEstimate(
                            beta_per_bp=spread_beta,
                            dv01_proxy_per_share=None if spread_beta is None else abs(spread_beta) * latest_price,
                            regression_r2=ewma_blend([headline_120d["regression_r2"], headline_60d["regression_r2"]]),
                            proxy_used=selection.spread_proxy_series_id,
                        )
                    if headline_60d["estimated_duration"] is None or headline_120d["estimated_duration"] is None:
                        headline_60d = regress_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
                        headline_120d = regress_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)
                elif len(benchmark_frame) >= 20:
                    headline_60d = regress_benchmark_duration(benchmark_frame.tail(60), 60, benchmark_duration)
                    headline_120d = regress_benchmark_duration(benchmark_frame.tail(120), 120, benchmark_duration)
        elif selection.spread_proxy_series_id:
            spread_series = spread_changes_bps(self.macro_store, selection.spread_proxy_series_id, start_date=start_date)
            if not spread_series.empty:
                spread_frame = aligned.join(spread_series, how="inner")
                if len(spread_frame) >= 20:
                    spread_60d = regress_duration(spread_frame.tail(60), 60, [*RATE_SERIES, "spread_change_bps"])
                    spread_120d = regress_duration(spread_frame.tail(120), 120, [*RATE_SERIES, "spread_change_bps"])
                    spread_beta = ewma_blend([spread_120d["credit_beta"], spread_60d["credit_beta"]])
                    spread_estimate = SpreadRiskEstimate(
                        beta_per_bp=spread_beta,
                        dv01_proxy_per_share=None if spread_beta is None else abs(spread_beta) * latest_price,
                        regression_r2=ewma_blend([spread_120d["regression_r2"], spread_60d["regression_r2"]]),
                        proxy_used=selection.spread_proxy_series_id,
                    )

        estimated_duration = ewma_blend([headline_120d["estimated_duration"], headline_60d["estimated_duration"]])
        rate_model_r2 = ewma_blend([headline_120d["regression_r2"], headline_60d["regression_r2"]])
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
            rate_risk=RateRiskEstimate(
                estimated_duration=estimated_duration,
                dv01_per_share=None if estimated_duration is None else estimated_duration * latest_price * 0.0001,
                ir01_per_share=None if estimated_duration is None else estimated_duration * latest_price * 0.0001,
                regression_r2=rate_model_r2,
                benchmark_used=selection.treasury_benchmark_symbol,
                rate_proxy_used=selection.rate_proxy_description,
                lookback_days_used=120 if headline_120d["estimated_duration"] is not None else headline_60d["lookback_days_used"],
                observations_used=headline_120d["observations_used"] or headline_60d["observations_used"],
            ),
            spread_risk=spread_estimate,
        )

    def _benchmark_duration_proxy(self, benchmark_ticker: str, start_date: str) -> float | None:
        benchmark_history = self.price_store.get_ticker_price_history(benchmark_ticker, start_date=start_date)
        if benchmark_history.empty:
            return None
        benchmark = Security(benchmark_ticker, history=benchmark_history)
        returns = benchmark.log_returns()
        if returns.empty:
            return None
        rate_changes_bps = treasury_rate_changes_bps(self.macro_store, start_date=start_date)
        if rate_changes_bps.empty or any(series_id not in rate_changes_bps.columns for series_id in RATE_SERIES):
            return None
        aligned = returns.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
        if len(aligned) < 20:
            return None
        model_60d = regress_duration(aligned.tail(60), 60, list(RATE_SERIES))
        model_120d = regress_duration(aligned.tail(120), 120, list(RATE_SERIES))
        return ewma_blend([model_120d["estimated_duration"], model_60d["estimated_duration"]])

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
                rate_proxy_used=selection.rate_proxy_description or RATE_FACTOR_LABEL,
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
