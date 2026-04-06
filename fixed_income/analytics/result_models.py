from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DurationModelSelection:
    asset_bucket: str
    duration_model_type: str
    treasury_benchmark_symbol: str | None
    spread_proxy_series_id: str | None
    rate_proxy_description: str
    confidence_level: str
    notes: str
    used_fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RateRiskEstimate:
    estimated_duration: float | None
    dv01_per_share: float | None
    ir01_per_share: float | None
    regression_r2: float | None
    benchmark_used: str | None
    rate_proxy_used: str
    lookback_days_used: int | None
    observations_used: int | None


@dataclass(frozen=True)
class SpreadRiskEstimate:
    beta_per_bp: float | None
    dv01_proxy_per_share: float | None
    regression_r2: float | None
    proxy_used: str | None


@dataclass(frozen=True)
class EquityRiskEstimate:
    beta: float | None = None
    proxy_used: str | None = None
    regression_r2: float | None = None


@dataclass(frozen=True)
class SecurityAnalyticsSnapshot:
    ticker: str
    asset_bucket: str
    model_type_used: str
    confidence_level: str
    notes: str
    reason: str | None
    rate_risk: RateRiskEstimate
    spread_risk: SpreadRiskEstimate | None = None
    equity_risk: EquityRiskEstimate | None = None

    @property
    def benchmark_used(self) -> str | None:
        return self.rate_risk.benchmark_used

    @property
    def rate_proxy_used(self) -> str:
        return self.rate_risk.rate_proxy_used

    @property
    def estimated_duration(self) -> float | None:
        return self.rate_risk.estimated_duration

    @property
    def dv01_per_share(self) -> float | None:
        return self.rate_risk.dv01_per_share

    @property
    def ir01_per_share(self) -> float | None:
        return self.rate_risk.ir01_per_share

    @property
    def rate_model_r2(self) -> float | None:
        return self.rate_risk.regression_r2

    @property
    def spread_beta_per_bp(self) -> float | None:
        return None if self.spread_risk is None else self.spread_risk.beta_per_bp

    @property
    def spread_model_r2(self) -> float | None:
        return None if self.spread_risk is None else self.spread_risk.regression_r2

    @property
    def spread_proxy_used(self) -> str | None:
        return None if self.spread_risk is None else self.spread_risk.proxy_used

    @property
    def spread_dv01_proxy_per_share(self) -> float | None:
        return None if self.spread_risk is None else self.spread_risk.dv01_proxy_per_share

    @property
    def observations_used(self) -> int | None:
        return self.rate_risk.observations_used
