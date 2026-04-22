from __future__ import annotations

from fixed_income.analytics.result_models import DurationModelSelection
from fixed_income.config.bucket_rules import classify_bucket
from fixed_income.config.spread_proxy_rules import spread_proxy_for_bucket


class DurationModelSelector:
    """Route fixed-income instruments into benchmark and spread models."""

    def select_for_security(self, security) -> DurationModelSelection:
        bucket = classify_bucket(security)
        benchmark = None
        model_type = "treasury_curve_regression"
        notes = ""
        confidence = "medium"
        used_fallback = False

        if bucket in {"Treasury", "Inflation-Linked"}:
            notes = "Rates estimated directly from Treasury curve factors."
            confidence = "high"
        elif bucket in {"Short Duration / Cash-like", "Floating Rate"}:
            model_type = "low_duration_assumption_with_validation"
            benchmark = "SHY"
            notes = "Short-duration funds are validated against a short Treasury benchmark."
            confidence = "high"
        elif bucket == "Investment Grade Credit":
            benchmark = "IEF"
            model_type = "treasury_etf_benchmark_regression"
            confidence = "high"
            notes = "Investment Grade Credit routed to Treasury ETF benchmark regression."
        elif bucket == "High Yield":
            benchmark = "SHY"
            model_type = "treasury_etf_benchmark_regression"
            confidence = "high"
            notes = "High Yield routed to Treasury ETF benchmark regression."
        elif bucket == "Muni":
            benchmark = "IEF"
            model_type = "treasury_etf_benchmark_regression"
            confidence = "high"
            notes = "Muni routed to Treasury ETF benchmark regression."
        elif bucket == "Mortgage / Securitized":
            benchmark = "VGIT"
            model_type = "treasury_etf_benchmark_regression"
            confidence = "high"
            notes = "Mortgage / Securitized routed to Treasury ETF benchmark regression."
        elif bucket == "Preferred / Hybrid":
            benchmark = "IEF"
            model_type = "treasury_etf_benchmark_regression"
            confidence = "high"
            notes = "Preferred / Hybrid routed to Treasury ETF benchmark regression."
        else:
            notes = "Unknown bucket fell back to Treasury curve regression."
            confidence = "low"
            used_fallback = True

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
