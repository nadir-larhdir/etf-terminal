from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from fixed_income.analytics.factor_data import spread_changes_bps, treasury_rate_changes_bps
from fixed_income.analytics.rate_models import ewma_blend, regress_benchmark_duration, regress_duration
from fixed_income.analytics.result_models import RateRiskEstimate, SecurityAnalyticsSnapshot, SpreadRiskEstimate
from fixed_income.analytics.spread_models import regress_credit_benchmark_duration
from fixed_income.config.benchmark_rules import BENCHMARK_POOL
from fixed_income.config.model_settings import ANALYTICS_MODEL_VERSION, RATE_FACTOR_LABEL, RATE_SERIES
from fixed_income.config.spread_proxy_rules import SPREAD_PROXY_BY_BUCKET
from fixed_income.instruments.security import Security


LOGGER = logging.getLogger(__name__)


class FixedIncomeAnalyticsService:
    """Estimate rate and spread risk for fixed-income instruments from stored data."""

    def __init__(self, price_store, macro_store, duration_selector, analytics_snapshot_store=None) -> None:
        self.price_store = price_store
        self.macro_store = macro_store
        self.duration_selector = duration_selector
        self.analytics_snapshot_store = analytics_snapshot_store

    def model_settings_key(self) -> str:
        spread_series = sorted({series_id for series_id in SPREAD_PROXY_BY_BUCKET.values() if series_id})
        return "|".join([*RATE_SERIES, *spread_series])

    def latest_macro_factor_date(self) -> str | None:
        series_ids = [*RATE_SERIES, *sorted({series_id for series_id in SPREAD_PROXY_BY_BUCKET.values() if series_id})]
        latest_dates = self.macro_store.get_latest_stored_dates(series_ids)
        return max(latest_dates.values()) if latest_dates else None

    def get_latest_snapshot(self, symbol: str) -> SecurityAnalyticsSnapshot | None:
        if self.analytics_snapshot_store is None:
            return None
        return self.analytics_snapshot_store.get_latest_snapshot(symbol)

    def persist_snapshot(self, snapshot: SecurityAnalyticsSnapshot, *, as_of_date: str) -> None:
        if self.analytics_snapshot_store is None:
            return
        self.analytics_snapshot_store.upsert_snapshot(snapshot, as_of_date=as_of_date)

    def analyze_security(self, security: Security) -> SecurityAnalyticsSnapshot:
        factor_bundle = self.load_factor_bundle(security)
        return self.analyze_factor_bundle(security, factor_bundle)

    def load_factor_bundle(self, security: Security) -> dict[str, object]:
        returns = security.log_returns()
        latest_price = security.last_price()
        start_date = None if returns.empty else (returns.index.max() - pd.Timedelta(days=260)).date().isoformat()
        rate_changes_bps = treasury_rate_changes_bps(self.macro_store, start_date=start_date) if start_date else pd.DataFrame()
        if start_date and hasattr(self.price_store, "get_multi_ticker_price_history"):
            benchmark_history = self.price_store.get_multi_ticker_price_history(list(BENCHMARK_POOL), start_date=start_date)
        elif start_date:
            benchmark_history = {
                ticker: self.price_store.get_ticker_price_history(ticker, start_date=start_date) for ticker in BENCHMARK_POOL
            }
        else:
            benchmark_history = {}
        benchmark_returns_map: dict[str, pd.Series] = {}
        for benchmark_ticker, history in benchmark_history.items():
            if history.empty:
                continue
            benchmark_security = Security(benchmark_ticker, history=history)
            series = benchmark_security.log_returns()
            if not series.empty:
                benchmark_returns_map[benchmark_ticker] = series.rename("benchmark_return")

        spread_series_map: dict[str, pd.Series] = {}
        for series_id in sorted({series for series in SPREAD_PROXY_BY_BUCKET.values() if series}):
            spread_series = spread_changes_bps(self.macro_store, series_id, start_date=start_date) if start_date else pd.Series(dtype=float)
            if not spread_series.empty:
                spread_series_map[series_id] = spread_series

        benchmark_duration_map = {
            benchmark_ticker: self._regressed_benchmark_duration(
                benchmark_returns_map.get(benchmark_ticker, pd.Series(dtype=float)),
                rate_changes_bps,
            )
            for benchmark_ticker in BENCHMARK_POOL
        }

        return {
            "returns": returns.rename("etf_return"),
            "latest_price": latest_price,
            "start_date": start_date,
            "rate_changes_bps": rate_changes_bps,
            "benchmark_returns": benchmark_returns_map,
            "benchmark_durations": benchmark_duration_map,
            "spread_series": spread_series_map,
        }

    def analyze_factor_bundle(self, security: Security, factor_bundle: dict[str, object]) -> SecurityAnalyticsSnapshot:
        returns = factor_bundle["returns"]
        latest_price = factor_bundle["latest_price"]
        if returns.empty or latest_price is None:
            return self._empty_snapshot(security, "Insufficient ETF price history.")

        start_date = factor_bundle["start_date"]
        rate_changes_bps = factor_bundle["rate_changes_bps"]
        if rate_changes_bps.empty:
            return self._empty_snapshot(security, "Treasury rate history is unavailable.")

        missing = [series_id for series_id in RATE_SERIES if series_id not in rate_changes_bps.columns]
        if missing:
            return self._empty_snapshot(security, f"Missing Treasury series: {', '.join(missing)}.")

        aligned = returns.to_frame().join(rate_changes_bps, how="inner")
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
            benchmark_duration = self._benchmark_duration_proxy(
                selection.treasury_benchmark_symbol,
                factor_bundle["benchmark_durations"],
            )
            benchmark_series = factor_bundle["benchmark_returns"].get(selection.treasury_benchmark_symbol, pd.Series(dtype=float))
            if benchmark_duration is not None and not benchmark_series.empty:
                benchmark_frame = aligned.join(benchmark_series.rename("benchmark_return"), how="inner")
                if selection.spread_proxy_series_id:
                    spread_series = factor_bundle["spread_series"].get(selection.spread_proxy_series_id, pd.Series(dtype=float))
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
            spread_series = factor_bundle["spread_series"].get(selection.spread_proxy_series_id, pd.Series(dtype=float))
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

        as_of_date = None if security.history.empty else pd.Timestamp(security.history.index.max()).date().isoformat()
        LOGGER.info("Analytics live compute for %s (as_of=%s)", security.ticker, as_of_date)
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
                regression_r2=rate_model_r2,
                benchmark_used=selection.treasury_benchmark_symbol,
                rate_proxy_used=selection.rate_proxy_description,
                lookback_days_used=120 if headline_120d["estimated_duration"] is not None else headline_60d["lookback_days_used"],
                observations_used=headline_120d["observations_used"] or headline_60d["observations_used"],
            ),
            spread_risk=spread_estimate,
            as_of_date=as_of_date,
            updated_at=datetime.utcnow().isoformat(),
            model_version=ANALYTICS_MODEL_VERSION,
            computed_from_start_date=start_date,
            computed_from_end_date=as_of_date,
        )

    def _benchmark_duration_proxy(
        self,
        benchmark_ticker: str,
        benchmark_duration_map: dict[str, float | None],
    ) -> float | None:
        return benchmark_duration_map.get(benchmark_ticker)

    def _regressed_benchmark_duration(
        self,
        benchmark_returns_series: pd.Series,
        rate_changes_bps: pd.DataFrame,
    ) -> float | None:
        if benchmark_returns_series.empty or rate_changes_bps.empty:
            return None
        if any(series_id not in rate_changes_bps.columns for series_id in RATE_SERIES):
            return None
        aligned = benchmark_returns_series.rename("etf_return").to_frame().join(rate_changes_bps, how="inner")
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
            as_of_date=None if security.history.empty else pd.Timestamp(security.history.index.max()).date().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
            model_version=ANALYTICS_MODEL_VERSION,
            computed_from_start_date=None,
            computed_from_end_date=None if security.history.empty else pd.Timestamp(security.history.index.max()).date().isoformat(),
        )
