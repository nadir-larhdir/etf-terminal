from __future__ import annotations

from typing import TYPE_CHECKING

from fixed_income.analytics.result_models import RiskProxySelection
from fixed_income.config.bucket_rules import classify_bucket
from fixed_income.config.spread_proxy_rules import spread_proxy_for_bucket

if TYPE_CHECKING:
    from fixed_income.etfs import ETF


class RiskProxySelector:
    """Classify ETFs and choose spread-risk proxy series."""

    def select_for_etf(self, etf: ETF) -> RiskProxySelection:
        bucket = classify_bucket(etf)
        return RiskProxySelection(
            asset_bucket=bucket,
            spread_proxy_series_id=spread_proxy_for_bucket(bucket, etf),
        )
