from __future__ import annotations

from fixed_income.analytics.result_models import DurationModelSelection
from fixed_income.config.benchmark_rules import FALLBACK_OVERRIDES, benchmark_for_bucket
from fixed_income.config.bucket_rules import classify_bucket
from fixed_income.config.spread_proxy_rules import spread_proxy_for_bucket


class DurationModelSelector:
    """Route fixed-income instruments into benchmark and spread models."""

    def select_for_security(self, security, rough_duration: float | None = None) -> DurationModelSelection:
        if security.ticker in FALLBACK_OVERRIDES:
            override = FALLBACK_OVERRIDES[security.ticker].copy()
            override["spread_proxy_series_id"] = spread_proxy_for_bucket(override["asset_bucket"], security)
            return DurationModelSelection(**override)

        bucket = classify_bucket(security)
        benchmark = None
        model_type = "treasury_curve_regression"
        notes = ""
        confidence = "medium"
        used_fallback = False

        if bucket in {"Treasury", "Inflation-Linked"}:
            notes = "Rates estimated directly from Treasury curve factors."
            confidence = "high"
        elif bucket == "Floating Rate":
            model_type = "low_duration_assumption_with_validation"
            benchmark = "SHY"
            notes = "Floating-rate funds are validated against a short-duration benchmark."
        else:
            model_type = "treasury_etf_benchmark_regression"
            benchmark = benchmark_for_bucket(bucket, rough_duration, security)
            confidence = "high" if bucket != "Unknown" else "low"
            notes = (
                "Unknown bucket fell back to a rule-based Treasury ETF benchmark."
                if bucket == "Unknown"
                else f"{bucket} routed to Treasury ETF benchmark regression."
            )
            used_fallback = bucket == "Unknown"

        description = (
            "Treasury curve regression using DGS2, DGS5, DGS10, and DGS30."
            if benchmark is None
            else f"Treasury ETF benchmark regression using {benchmark}."
        )
        return DurationModelSelection(
            asset_bucket=bucket,
            duration_model_type=model_type,
            treasury_benchmark_symbol=benchmark,
            spread_proxy_series_id=spread_proxy_for_bucket(bucket, security),
            rate_proxy_description=description,
            confidence_level=confidence,
            notes=notes,
            used_fallback=used_fallback,
        )
