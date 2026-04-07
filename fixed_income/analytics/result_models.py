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
    as_of_date: str | None = None
    updated_at: str | None = None
    model_version: str | None = None
    computed_from_start_date: str | None = None
    computed_from_end_date: str | None = None

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

    def to_record(self) -> dict[str, Any]:
        return {
            "symbol": self.ticker,
            "as_of_date": self.as_of_date,
            "asset_bucket": self.asset_bucket,
            "benchmark_used": self.benchmark_used,
            "spread_proxy_used": self.spread_proxy_used,
            "estimated_duration": self.estimated_duration,
            "rate_dv01_per_share": self.dv01_per_share,
            "cs01_proxy_per_share": self.spread_dv01_proxy_per_share,
            "spread_beta_per_bp": self.spread_beta_per_bp,
            "equity_beta": None if self.equity_risk is None else self.equity_risk.beta,
            "rate_model_r2": self.rate_model_r2,
            "spread_model_r2": self.spread_model_r2,
            "confidence_level": self.confidence_level,
            "model_type": self.model_type_used,
            "rate_proxy_used": self.rate_proxy_used,
            "notes": self.notes,
            "reason": self.reason,
            "lookback_days_used": self.rate_risk.lookback_days_used,
            "observations_used": self.observations_used,
            "updated_at": self.updated_at,
            "model_version": self.model_version,
            "computed_from_start_date": self.computed_from_start_date,
            "computed_from_end_date": self.computed_from_end_date,
        }

    @classmethod
    def from_record(cls, row: dict[str, Any]) -> "SecurityAnalyticsSnapshot":
        return cls(
            ticker=str(row["symbol"]),
            asset_bucket=str(row.get("asset_bucket") or "Unknown"),
            model_type_used=str(row.get("model_type") or "unknown"),
            confidence_level=str(row.get("confidence_level") or "unknown"),
            notes=str(row.get("notes") or ""),
            reason=row.get("reason"),
            rate_risk=RateRiskEstimate(
                estimated_duration=row.get("estimated_duration"),
                dv01_per_share=row.get("rate_dv01_per_share"),
                ir01_per_share=row.get("rate_dv01_per_share"),
                regression_r2=row.get("rate_model_r2"),
                benchmark_used=row.get("benchmark_used"),
                rate_proxy_used=str(row.get("rate_proxy_used") or ""),
                lookback_days_used=row.get("lookback_days_used"),
                observations_used=row.get("observations_used"),
            ),
            spread_risk=(
                SpreadRiskEstimate(
                    beta_per_bp=row.get("spread_beta_per_bp"),
                    dv01_proxy_per_share=row.get("cs01_proxy_per_share"),
                    regression_r2=row.get("spread_model_r2"),
                    proxy_used=row.get("spread_proxy_used"),
                )
                if row.get("spread_proxy_used") or row.get("cs01_proxy_per_share") is not None
                else None
            ),
            equity_risk=(
                EquityRiskEstimate(
                    beta=row.get("equity_beta"),
                    proxy_used=None,
                    regression_r2=None,
                )
                if row.get("equity_beta") is not None
                else None
            ),
            as_of_date=None if row.get("as_of_date") is None else str(row.get("as_of_date")),
            updated_at=None if row.get("updated_at") is None else str(row.get("updated_at")),
            model_version=None if row.get("model_version") is None else str(row.get("model_version")),
            computed_from_start_date=None
            if row.get("computed_from_start_date") is None
            else str(row.get("computed_from_start_date")),
            computed_from_end_date=None
            if row.get("computed_from_end_date") is None
            else str(row.get("computed_from_end_date")),
        )
