import logging
import pandas as pd
import streamlit as st

from dashboard.cache import (
    app_cache_key,
    cached_live_analytics_snapshot,
    cached_precomputed_analytics_snapshot,
    is_snapshot_stale,
    restore_analytics_snapshot,
    snapshot_age_hours,
)
from dashboard.components.info_panel import InfoPanel
from dashboard.perf import timed_block
from fixed_income.analytics import format_model_label, format_oas_proxy_label
from fixed_income.instruments.security import Security


LOGGER = logging.getLogger(__name__)


class AnalyticsTab:
    """Display model-based ETF rate-risk and trading diagnostics."""

    def __init__(self, analytics_service) -> None:
        self.analytics_service = analytics_service
        self.info_panel = InfoPanel()

    def render(self, security: Security) -> None:
        st.subheader("Analytics")
        with timed_block("analytics.prepare_inputs"):
            metadata = security.metadata or {}
            asset_bucket = security.asset_class or metadata.get("category") or "N/A"
            snapshot = security.trading_snapshot()
            analytics = self._analytics_snapshot(security)
            liquidity_regime = self._liquidity_regime(snapshot["volume_z"])
            asset_regime = self._asset_regime_note(asset_bucket, metadata)

        a1, a2, a3, a4 = st.columns(4)
        with a1:
            self._render_highlight_metric("Estimated Duration", self._format_years(analytics.estimated_duration), "#C94F4F")
        with a2:
            st.metric("DV01 / IR01", self._format_dollar(analytics.dv01_per_share))
        with a3:
            st.metric("SPREAD BETA (PER BP)", self._format_spread_beta(analytics.spread_beta_per_bp))
        with a4:
            st.metric("SPREAD DV01 PROXY / SHARE", self._format_dollar(analytics.spread_dv01_proxy_per_share))

        if analytics.spread_proxy_used:
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                st.metric("BENCHMARK USED", analytics.benchmark_used or "Curve")
            with s2:
                st.metric("OAS PROXY USED", format_oas_proxy_label(analytics.spread_proxy_used))
            with s3:
                st.metric("RATE MODEL R²", self._format_number(analytics.rate_model_r2))
            with s4:
                st.metric("SPREAD MODEL R²", self._format_number(analytics.spread_model_r2))
        else:
            s1, s2 = st.columns(2)
            with s1:
                st.metric("BENCHMARK USED", analytics.benchmark_used or "Curve")
            with s2:
                st.metric("RATE MODEL R²", self._format_number(analytics.rate_model_r2))

        self.info_panel.render_note(
            title="Methodology Note",
            body=(
                "Estimated metrics are model-based proxies from ETF adjusted-close returns and Treasury yield changes. "
                "ICE BofA OAS spread inputs come from FRED and are measured in basis points for the spread regression. "
                "These are model-based proxies, not official published fund analytics or exact CS01. "
                "High-yield duration estimates are typically more sensitive than Treasury and IG estimates."
            ),
            accent_color="#FF9F1A",
            margin_top="0.30rem",
            margin_bottom="0.30rem",
        )

        tone = "orderly"
        if liquidity_regime == "HIGH ACTIVITY":
            tone = "elevated"
        elif liquidity_regime == "QUIET":
            tone = "subdued"

        duration_text = self._format_years(analytics.estimated_duration)
        dv01_text = self._format_dollar(analytics.dv01_per_share)
        reason_text = analytics.reason or (
            f"Estimated from smoothed 60D and 120D regressions using {analytics.rate_proxy_used}."
        )
        self.info_panel.render_note(
            title="Current Read",
            body=(
                f"{security.ticker} screens as {asset_regime}. Estimated duration is {duration_text} and DV01 is {dv01_text} "
                f"per share. Model: {format_model_label(analytics.model_type_used)}. "
                f"Benchmark: {analytics.benchmark_used or 'Curve factors'}. {reason_text} Trading participation is {tone}, "
                f"with volume at {self._volume_multiple(snapshot):.2f}x its 30-day average and the "
                f"latest close at {self._format_percent(snapshot['range_position'])} of today’s range."
            ),
            accent_color="#FF9F1A",
            margin_top="0.30rem",
            margin_bottom="0.30rem",
        )

        left, right = st.columns(2)
        with left:
            self.info_panel.render(
                title="Asset Bucket / Regime Note",
                headline=analytics.asset_bucket,
                body=f"{asset_regime} Confidence: {analytics.confidence_level}. {analytics.notes}",
                accent_color="#5DA9E9",
                margin_top="0.35rem",
                margin_bottom="0.20rem",
            )
            self.info_panel.render(
                title="Spread Beta Proxy",
                headline=self._format_spread_beta(analytics.spread_beta_per_bp) if analytics.spread_proxy_used else "N/A",
                body=(
                    f"ICE BofA OAS proxy from FRED: {format_oas_proxy_label(analytics.spread_proxy_used)}. "
                    f"Spread DV01 proxy / share: {self._format_dollar(analytics.spread_dv01_proxy_per_share)}. "
                    f"Spread model R²: {self._format_number(analytics.spread_model_r2)}. "
                    "This is a model-based spread sensitivity proxy per bp, not exact CS01."
                ),
                accent_color="#A78BFA",
                margin_top="0.35rem",
                margin_bottom="0.20rem",
            )
        with right:
            self.info_panel.render(
                title="Trading Activity",
                headline=liquidity_regime,
                body="Based on current volume versus the trailing 30-day average and its standardized z-score.",
                accent_color="#00ADB5",
                margin_top="0.35rem",
                margin_bottom="0.20rem",
            )
            self.info_panel.render(
                title="Model Diagnostics",
                headline=f"Rate R² {self._format_number(analytics.rate_model_r2)}",
                body=(
                    f"Rate proxy: {analytics.rate_proxy_used}. "
                    f"Spread model R²: {self._format_number(analytics.spread_model_r2)}. "
                    f"Observations used: {analytics.observations_used or 'N/A'}. "
                    f"60D/120D windows are smoothed with EWMA."
                ),
                accent_color="#FFD166",
                margin_top="0.35rem",
                margin_bottom="0.20rem",
            )

    def _analytics_snapshot(self, security: Security):
        cache_key = app_cache_key(self.analytics_service.price_store.engine)
        price_as_of = pd.Timestamp(security.history.index.max()).date().isoformat() if not security.history.empty else "n/a"
        with timed_block("analytics.fetch_precomputed_snapshot"):
            precomputed = restore_analytics_snapshot(
                cached_precomputed_analytics_snapshot(cache_key, security.ticker, self.analytics_service)
            )
        stale = is_snapshot_stale(precomputed, ttl_hours=24, required_as_of_date=price_as_of)
        if precomputed is not None and not stale:
            LOGGER.info(
                "Analytics snapshot hit for %s (age_hours=%.2f)",
                security.ticker,
                snapshot_age_hours(precomputed) or 0.0,
            )
            return precomputed
        LOGGER.info(
            "Analytics snapshot miss for %s (missing=%s stale=%s age_hours=%s)",
            security.ticker,
            precomputed is None,
            stale,
            "n/a" if precomputed is None else f"{(snapshot_age_hours(precomputed) or 0.0):.2f}",
        )

        macro_as_of = self.analytics_service.latest_macro_factor_date()
        settings_key = self.analytics_service.model_settings_key()
        with timed_block("analytics.compute_snapshot"):
            analytics = restore_analytics_snapshot(
                cached_live_analytics_snapshot(
                    cache_key,
                    security.ticker,
                    price_as_of,
                    macro_as_of,
                    settings_key,
                    security.history,
                    security.metadata or {},
                    security.asset_class,
                    security.name,
                    self.analytics_service,
                )
            )
        self.analytics_service.persist_snapshot(analytics, as_of_date=price_as_of)
        return analytics

    def _asset_regime_note(self, asset_bucket: str, metadata: dict) -> str:
        duration_bucket = str(metadata.get("duration_bucket") or "N/A")
        benchmark = str(metadata.get("benchmark_index") or "N/A")
        return f"{asset_bucket} exposure with a {duration_bucket.lower()} profile. Benchmark context: {benchmark}."

    def _format_dollar(self, value: float | None) -> str:
        return "N/A" if value is None else f"${value:.4f}"

    def _format_years(self, value: float | None) -> str:
        return "N/A" if value is None else f"{value:.1f}y"

    def _format_number(self, value: float | None) -> str:
        return "N/A" if value is None else f"{value:.2f}"

    def _format_spread_beta(self, value: float | None) -> str:
        return "N/A" if value is None else f"{value:+.5f}"

    def _format_percent(self, value: float | None) -> str:
        return "N/A" if value is None else f"{value:.0%}"

    def _render_highlight_metric(self, label: str, value: str, color: str) -> None:
        st.markdown(
            (
                "<div class='bb-highlight-metric'>"
                "<div class='bb-highlight-metric-label'>{label}</div>"
                "<div class='bb-highlight-metric-value' style='color:{color};'>{value}</div>"
                "</div>"
            ).format(label=label, value=value, color=color),
            unsafe_allow_html=True,
        )

    def _volume_multiple(self, snapshot: dict[str, float | None]) -> float:
        current_volume = snapshot["current_volume"]
        average_volume = snapshot["average_volume"]
        if current_volume is None or average_volume in (None, 0.0):
            return 0.0
        return current_volume / average_volume

    def _liquidity_regime(self, vol_z: float | None) -> str:
        if vol_z is None:
            return "NORMAL"
        if vol_z > 2:
            return "HIGH ACTIVITY"
        if vol_z < -1:
            return "QUIET"
        return "NORMAL"
