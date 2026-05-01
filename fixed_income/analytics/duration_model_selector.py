from __future__ import annotations

from fixed_income.analytics.result_models import DurationModelSelection
from fixed_income.config.bucket_rules import classify_bucket
from fixed_income.config.spread_proxy_rules import spread_proxy_for_bucket


class DurationModelSelector:
    """Classify securities for metadata-duration analytics and spread proxies."""

    def select_for_security(self, security) -> DurationModelSelection:
        bucket = classify_bucket(security)
        spread_proxy = spread_proxy_for_bucket(bucket, security)
        notes = "Duration is sourced from issuer metadata."
        if spread_proxy:
            notes = f"{notes} Spread beta uses {spread_proxy} changes."

        return DurationModelSelection(
            asset_bucket=bucket,
            duration_model_type="provider_metadata",
            treasury_benchmark_symbol=None,
            spread_proxy_series_id=spread_proxy,
            rate_proxy_description="Issuer published duration",
            confidence_level="high",
            notes=notes,
            used_fallback=False,
        )
