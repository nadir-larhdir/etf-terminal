from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pandas as pd

from fixed_income.analytics.factor_data import spread_changes_bps
from fixed_income.analytics.result_models import (
    ETFAnalyticsSnapshot,
    RateRiskEstimate,
    RiskProxySelection,
    SpreadRiskEstimate,
)
from fixed_income.analytics.risk_proxy_selector import RiskProxySelector
from fixed_income.analytics.spread_models import ewma_blend, regress_spread_beta
from fixed_income.config.model_settings import ANALYTICS_MODEL_VERSION
from fixed_income.config.spread_proxy_rules import SPREAD_PROXY_BY_BUCKET
from fixed_income.etfs import ETF

if TYPE_CHECKING:
    from stores.protocols import AnalyticsSnapshotStorage, MacroSeriesReader, PriceHistoryReader

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactorBundle:
    """Everything loaded from storage that one ETF's analytics run needs.

    A typed record rather than a dict so the loading step and the compute step share a
    checked contract and can be exercised independently.
    """

    returns: pd.Series
    latest_price: float | None
    start_date: str | None
    selection: RiskProxySelection
    spread_series: dict[str, pd.Series] = field(default_factory=dict)


METADATA_DURATION_MODEL_TYPE = "provider_metadata"
METADATA_DURATION_CONFIDENCE = "high"


class FixedIncomeAnalyticsService:
    """Build ETF analytics from provider metadata and spread-risk regressions."""

    def __init__(
        self,
        price_store: PriceHistoryReader,
        macro_store: MacroSeriesReader,
        risk_proxy_selector: RiskProxySelector,
        analytics_snapshot_store: AnalyticsSnapshotStorage | None = None,
    ) -> None:
        self.price_store = price_store
        self.macro_store = macro_store
        self.risk_proxy_selector = risk_proxy_selector
        self.analytics_snapshot_store = analytics_snapshot_store

    def model_settings_key(self) -> str:
        return "|".join(
            sorted({series_id for series_id in SPREAD_PROXY_BY_BUCKET.values() if series_id})
        )

    def latest_macro_factor_date(self) -> str | None:
        series_ids = sorted(
            {series_id for series_id in SPREAD_PROXY_BY_BUCKET.values() if series_id}
        )
        latest_dates = self.macro_store.get_latest_stored_dates(series_ids)
        return max(latest_dates.values()) if latest_dates else None

    def get_latest_snapshot(self, symbol: str) -> ETFAnalyticsSnapshot | None:
        if self.analytics_snapshot_store is None:
            return None
        snapshot = self.analytics_snapshot_store.get_latest_snapshot(symbol)
        return snapshot if isinstance(snapshot, ETFAnalyticsSnapshot) else None

    def persist_snapshot(self, snapshot: ETFAnalyticsSnapshot, *, as_of_date: str) -> None:
        if self.analytics_snapshot_store is None:
            return
        self.analytics_snapshot_store.upsert_snapshot(snapshot, as_of_date=as_of_date)

    def analyze_etf(self, etf: ETF) -> ETFAnalyticsSnapshot:
        factor_bundle = self.load_etf_factor_bundle(etf)
        return self.analyze_factor_bundle(etf, factor_bundle)

    def load_etf_factor_bundle(self, etf: ETF) -> FactorBundle:
        returns = etf.log_returns().rename("etf_return")
        start_date = (
            None
            if returns.empty
            else (returns.index.max() - pd.Timedelta(days=260)).date().isoformat()
        )
        selection = self.risk_proxy_selector.select_for_etf(etf)

        spread_series_map: dict[str, pd.Series] = {}
        if start_date and selection.spread_proxy_series_id:
            spread_series = spread_changes_bps(
                self.macro_store, selection.spread_proxy_series_id, start_date=start_date
            )
            if not spread_series.empty:
                spread_series_map[selection.spread_proxy_series_id] = spread_series

        return FactorBundle(
            returns=returns,
            latest_price=etf.last_price(),
            start_date=start_date,
            selection=selection,
            spread_series=spread_series_map,
        )

    def analyze_factor_bundle(self, etf: ETF, factor_bundle: FactorBundle) -> ETFAnalyticsSnapshot:
        returns = factor_bundle.returns
        latest_price = factor_bundle.latest_price
        selection = factor_bundle.selection
        as_of_date = self._etf_as_of_date(etf)
        estimated_duration = etf.metadata_number("duration")

        if returns.empty or latest_price is None:
            return self._empty_snapshot(
                etf,
                "Insufficient ETF price history.",
                selection=selection,
                as_of_date=as_of_date,
            )
        if estimated_duration is None:
            return self._empty_snapshot(
                etf,
                "Provider duration is missing from ETF metadata.",
                selection=selection,
                as_of_date=as_of_date,
            )

        spread_estimate = self._spread_estimate(
            returns=returns,
            spread_series_map=factor_bundle.spread_series,
            spread_proxy_series_id=selection.spread_proxy_series_id,
            latest_price=latest_price,
        )
        observations_used = None if spread_estimate is None else spread_estimate.observations_used

        LOGGER.info("Analytics live compute for %s (as_of=%s)", etf.ticker, as_of_date)
        return ETFAnalyticsSnapshot(
            ticker=etf.ticker,
            asset_bucket=selection.asset_bucket,
            model_type_used=METADATA_DURATION_MODEL_TYPE,
            confidence_level=METADATA_DURATION_CONFIDENCE,
            notes=self._snapshot_notes(selection.spread_proxy_series_id),
            reason=None,
            rate_risk=RateRiskEstimate(
                estimated_duration=estimated_duration,
                dv01_per_share=estimated_duration * latest_price * 0.0001,
                observations_used=observations_used,
            ),
            spread_risk=spread_estimate,
            as_of_date=as_of_date,
            updated_at=datetime.now(UTC).isoformat(),
            model_version=ANALYTICS_MODEL_VERSION,
            computed_from_start_date=factor_bundle.start_date,
            computed_from_end_date=as_of_date,
        )

    def _spread_estimate(
        self,
        *,
        returns: pd.Series,
        spread_series_map: dict[str, pd.Series],
        spread_proxy_series_id: str | None,
        latest_price: float,
    ) -> SpreadRiskEstimate | None:
        if not spread_proxy_series_id:
            return None
        spread_series = spread_series_map.get(spread_proxy_series_id, pd.Series(dtype=float))
        if spread_series.empty:
            return SpreadRiskEstimate(
                beta_per_bp=None,
                dv01_proxy_per_share=None,
                regression_r2=None,
                proxy_used=spread_proxy_series_id,
                lookback_days_used=None,
                observations_used=None,
            )

        models = []
        spread_frame = returns.to_frame().join(spread_series, how="inner")
        if len(spread_frame) >= 20:
            models = [
                regress_spread_beta(spread_frame.tail(120), 120),
                regress_spread_beta(spread_frame.tail(60), 60),
            ]

        spread_beta = ewma_blend([model.get("credit_beta") for model in models])
        regression_r2 = ewma_blend([model.get("regression_r2") for model in models])
        observations_used = next(
            (model.get("observations_used") for model in models if model.get("observations_used")),
            None,
        )
        lookback_days_used = next(
            (
                model.get("lookback_days_used")
                for model in models
                if model.get("lookback_days_used")
            ),
            None,
        )
        return SpreadRiskEstimate(
            beta_per_bp=spread_beta,
            dv01_proxy_per_share=None if spread_beta is None else abs(spread_beta) * latest_price,
            regression_r2=regression_r2,
            proxy_used=spread_proxy_series_id,
            lookback_days_used=lookback_days_used,
            observations_used=observations_used,
        )

    def _empty_snapshot(
        self,
        etf: ETF,
        reason: str,
        *,
        selection: RiskProxySelection | None = None,
        as_of_date: str | None = None,
    ) -> ETFAnalyticsSnapshot:
        selection = selection or self.risk_proxy_selector.select_for_etf(etf)
        as_of_date = as_of_date or self._etf_as_of_date(etf)
        return ETFAnalyticsSnapshot(
            ticker=etf.ticker,
            asset_bucket=selection.asset_bucket,
            model_type_used=METADATA_DURATION_MODEL_TYPE,
            confidence_level=METADATA_DURATION_CONFIDENCE,
            notes=self._snapshot_notes(selection.spread_proxy_series_id),
            reason=reason,
            rate_risk=RateRiskEstimate(
                estimated_duration=None,
                dv01_per_share=None,
                observations_used=None,
            ),
            spread_risk=(
                SpreadRiskEstimate(
                    beta_per_bp=None,
                    dv01_proxy_per_share=None,
                    regression_r2=None,
                    proxy_used=selection.spread_proxy_series_id,
                    lookback_days_used=None,
                    observations_used=None,
                )
                if selection.spread_proxy_series_id
                else None
            ),
            as_of_date=as_of_date,
            updated_at=datetime.now(UTC).isoformat(),
            model_version=ANALYTICS_MODEL_VERSION,
            computed_from_start_date=None,
            computed_from_end_date=as_of_date,
        )

    def _etf_as_of_date(self, etf: ETF) -> str | None:
        if etf.history.empty:
            return None
        return str(pd.Timestamp(etf.history.index.max()).date().isoformat())

    def _snapshot_notes(self, spread_proxy_series_id: str | None) -> str:
        notes = "Duration is sourced from issuer metadata."
        if spread_proxy_series_id:
            notes = f"{notes} Spread beta uses {spread_proxy_series_id} changes."
        return notes
