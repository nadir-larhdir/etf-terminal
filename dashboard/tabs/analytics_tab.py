"""Analytics tab: duration, DV01, spread beta, volume bars, and current-read narrative panel."""

import logging

import pandas as pd
import plotly.graph_objects as go
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
from dashboard.mobile import PLOTLY_CHART_CONFIG
from dashboard.perf import timed_block
from fixed_income.analytics import format_oas_proxy_label
from fixed_income.instruments.security import Security
from services.market.duration_estimator import CURVE_REGRESSION_TICKERS, ISHARES_ETFS, PROXY_MAP

LOGGER = logging.getLogger(__name__)


class AnalyticsTab:
    """Display model-based ETF rate-risk and trading diagnostics."""

    def __init__(self, analytics_service) -> None:
        self.analytics_service = analytics_service
        self.info_panel = InfoPanel()

    def render(self, security: Security) -> None:
        """Render the Analytics tab: metric cards, credit spread section, volume bars, and narrative panels."""
        st.subheader("Analytics")
        with timed_block("analytics.prepare_inputs"):
            metadata = security.metadata or {}
            snapshot = security.trading_snapshot()
            analytics = self._analytics_snapshot(security)
            has_credit_spread = (
                analytics.spread_proxy_used is not None and analytics.spread_beta_per_bp is not None
            )
            liquidity_regime = self._liquidity_regime(snapshot["volume_z"])
            duration_method, duration_source = self._duration_source_details(security)
            duration_footer = self._duration_scale_indicator(analytics.estimated_duration)
            dv01_footer = self._dv01_change_footer(security, analytics.estimated_duration)

        a1, a2, a3, a4 = st.columns(4)
        with a1:
            self._render_metric_card(
                "Estimated Duration",
                self._format_years(analytics.estimated_duration),
                self._duration_risk_color(analytics.estimated_duration),
                "#5DA9E9",
                footer=duration_footer,
            )
        with a2:
            self._render_metric_card(
                "DV01 / $1MM",
                self._format_dollar_per_million(analytics.dv01_per_share),
                self._dv01_risk_color(analytics.dv01_per_share),
                "#5DA9E9",
                footer=dv01_footer,
            )
        with a3:
            self._render_metric_card("Duration Method", duration_method, "#1F271C", "#8D8779")
        with a4:
            self._render_metric_card("Duration Source", duration_source, "#1F271C", "#8D8779")

        st.markdown(
            "<div style='height:1px;margin:1.2rem 0 1.4rem 0;background:linear-gradient(90deg, rgba(95,141,132,0.0), rgba(95,141,132,0.45), rgba(111,123,70,0.35), rgba(111,123,70,0.0));'></div>",
            unsafe_allow_html=True,
        )

        if has_credit_spread:
            s1, s2, s3, s4 = st.columns(4)
            with s1:
                self._render_metric_card(
                    "OAS Proxy Used",
                    format_oas_proxy_label(analytics.spread_proxy_used),
                    "#1F271C",
                    "#6F7B46",
                )
            with s2:
                self._render_metric_card(
                    "CS Beta",
                    self._format_spread_beta_bps(analytics.spread_beta_per_bp),
                    self._cs_beta_risk_color(analytics.spread_beta_per_bp),
                    "#6F7B46",
                )
            with s3:
                self._render_metric_card(
                    "Proxy CS01 / $1MM",
                    self._format_dollar_per_million(analytics.spread_dv01_proxy_per_share),
                    self._cs01_risk_color(analytics.spread_dv01_proxy_per_share),
                    "#6F7B46",
                )
            with s4:
                self._render_metric_card(
                    "Credit Spread R²",
                    self._format_number(analytics.spread_model_r2),
                    "#1F271C",
                    "#6F7B46",
                    show_bottom_border=False,
                    footer=(
                        f"{self._r2_gauge(analytics.spread_model_r2)}"
                        f"<div style='margin-top:0.35rem;'>"
                        f"{analytics.observations_used or 'N/A'} observations"
                        f"</div>"
                    ),
                )

        with st.expander("Methodology", expanded=False):
            st.markdown(
                "Estimated duration is sourced from holdings, a proxy ETF beta, or Treasury-curve regression depending on the fund. "
                "Spread beta is measured per 1 bp move in the selected ICE BofA OAS series. "
                "DV01 and proxy CS01 are shown on a $1MM notional-equivalent basis, not as official published fund analytics or exact CS01."
            )

        left, right = st.columns([3, 2])
        with left:
            self.info_panel.render(
                title="Current Read",
                headline=self._current_read_headline(security, metadata),
                body=self._current_read_body(
                    security, metadata, snapshot, analytics, duration_method, duration_source
                ),
                accent_color="#5F8D84",
                margin_top="0.50rem",
                margin_bottom="0.30rem",
            )
            if has_credit_spread:
                self.info_panel.render(
                    title="Spread Beta Proxy",
                    headline=None,
                    body=(
                        f"{self._format_spread_beta_bps(analytics.spread_beta_per_bp)} vs {format_oas_proxy_label(analytics.spread_proxy_used)}.<br>"
                        f"{self._oas_move_explanation(analytics)} Proxy CS01: {self._format_dollar_per_million(analytics.spread_dv01_proxy_per_share)}/$1MM "
                        f"(R²: {self._format_number(analytics.spread_model_r2)})."
                    ),
                    accent_color="#6F7B46",
                    margin_top="0.50rem",
                    margin_bottom="0.30rem",
                )
        with right:
            self.info_panel.render(
                title="Trading Activity",
                headline=liquidity_regime,
                body=f"Current volume is running at {self._volume_multiple(snapshot):.2f}x the 30-day average.",
                accent_color="#5F8D84",
                margin_top="0.50rem",
                margin_bottom="0.12rem",
            )
            self._render_volume_bars(security)

    def _analytics_snapshot(self, security: Security):
        """Return a live or cached analytics snapshot, falling back to live computation when stale."""
        cache_key = app_cache_key(self.analytics_service.price_store.engine)
        price_as_of = (
            pd.Timestamp(security.history.index.max()).date().isoformat()
            if not security.history.empty
            else "n/a"
        )
        metadata_duration = self._metadata_duration(security.metadata or {})
        with timed_block("analytics.fetch_precomputed_snapshot"):
            precomputed = restore_analytics_snapshot(
                cached_precomputed_analytics_snapshot(
                    cache_key,
                    security.ticker,
                    price_as_of,
                    metadata_duration,
                    self.analytics_service,
                )
            )
        stale = is_snapshot_stale(
            precomputed,
            ttl_hours=24,
            required_as_of_date=price_as_of,
            required_estimated_duration=metadata_duration,
        )
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
                    metadata_duration,
                    security.history,
                    security.metadata or {},
                    security.asset_class,
                    security.name,
                    self.analytics_service,
                )
            )
        self.analytics_service.persist_snapshot(analytics, as_of_date=price_as_of)
        return analytics

    def _metadata_duration(self, metadata: dict) -> float | None:
        """Extract and cast the duration field from metadata, returning None for missing or non-numeric values."""
        raw_value = metadata.get("duration")
        if raw_value in (None, "", "N/A"):
            return None
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    def _current_read_headline(self, security: Security, metadata: dict) -> str:
        """Build the headline string for the Current Read panel from category and duration bucket."""
        category = str(metadata.get("category") or security.asset_class or "Fixed Income")
        duration_bucket = str(metadata.get("duration_bucket") or "").strip()
        if duration_bucket and duration_bucket.upper() != "N/A":
            return f"{duration_bucket} {category}"
        return category

    def _current_read_body(
        self,
        security: Security,
        metadata: dict,
        snapshot: dict[str, float | None],
        analytics,
        duration_method: str,
        duration_source: str,
    ) -> str:
        """Build the body text for the Current Read panel with benchmark, duration, and DV01 summary."""
        benchmark = str(metadata.get("benchmark_index") or "N/A")
        return (
            f"Benchmark: {benchmark}. Duration is {self._format_years(analytics.estimated_duration)} and DV01 is "
            f"{self._format_dollar_per_million(analytics.dv01_per_share)} per $1MM from {duration_method.lower()} "
            f"({duration_source})."
        )

    def _format_dollar_per_million(self, value: float | None) -> str:
        """Format a per-share dollar risk as a dollar amount per $1MM notional."""
        return "N/A" if value is None else f"${value * 10000:,.0f}"

    def _format_years(self, value: float | None) -> str:
        """Format a duration in years to one decimal place."""
        return "N/A" if value is None else f"{value:.1f}y"

    def _format_number(self, value: float | None) -> str:
        """Format a float to 2 decimal places."""
        return "N/A" if value is None else f"{value:.2f}"

    def _format_spread_beta_bps(self, value: float | None) -> str:
        """Format a spread beta (per decimal) as a signed basis-point string."""
        return "N/A" if value is None else f"{value * 10000:+.1f} bps"

    def _format_percent(self, value: float | None) -> str:
        """Format a decimal proportion as a whole-number percentage string."""
        return "N/A" if value is None else f"{value:.0%}"

    def _format_bps_impact(self, value: float | None) -> str:
        """Format a signed basis-point price impact to 2 decimal places."""
        return "N/A" if value is None else f"{value:+.2f} bps"

    def _oas_move_explanation(self, analytics) -> str:
        """Return a plain-English sentence describing the price impact of a +1 bp OAS move."""
        if analytics.spread_beta_per_bp is None or not analytics.spread_proxy_used:
            return "OAS 1 bp move interpretation unavailable."
        impact_bps = analytics.spread_beta_per_bp * 10000.0
        return f"+1bp OAS widening -> {self._format_bps_impact(impact_bps)} price change."

    def _duration_source_details(self, security: Security) -> tuple[str, str]:
        """Return a (method, source) label pair describing how duration was estimated for this ticker."""
        ticker = security.ticker.strip().upper()
        if ticker in ISHARES_ETFS:
            return ("Holdings", "PCF")
        if ticker in PROXY_MAP:
            return ("Proxy", PROXY_MAP[ticker])
        if ticker in CURVE_REGRESSION_TICKERS:
            return ("Regression", "Treasuries")
        return ("Model", "Derived")

    def _render_metric_card(
        self,
        label: str,
        value: str,
        color: str,
        border_color: str,
        *,
        footer: str | None = None,
        show_bottom_border: bool = True,
    ) -> None:
        """Render a single large-value metric card with a label, colored value, and optional footer HTML."""
        footer_block = ""
        if footer:
            footer_block = f"<div style='margin-top:0.45rem;color:#707A68;font-size:0.72rem;line-height:1.3;'>{footer}</div>"
        bottom_border = f"border-bottom:2px solid {border_color};" if show_bottom_border else ""
        st.markdown(
            (
                f"<div class='bb-highlight-metric' style='padding:0.25rem 0 0.85rem 0;{bottom_border}min-height:7.4rem;'>"
                f"<div class='bb-highlight-metric-label' style='font-size:0.68rem;letter-spacing:0.8px;text-transform:uppercase;color:#707A68;font-weight:600;'>{label}</div>"
                f"<div class='bb-highlight-metric-value' style='color:{color};font-size:3.35rem;font-weight:800;line-height:1.02;margin-top:0.18rem;'>{value}</div>"
                f"{footer_block}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    def _render_volume_bars(self, security: Security) -> None:
        """Render a 30-day bar chart of volume relative to the rolling 30D average."""
        history = security.history.copy()
        if history.empty or "volume" not in history.columns:
            return
        volume = history["volume"].astype(float)
        ratio = volume / volume.rolling(30, min_periods=5).mean()
        ratio = ratio.dropna().tail(30)
        if ratio.empty:
            return
        st.caption("Volume vs 30D average")
        fig = go.Figure(
            data=[
                go.Bar(
                    x=ratio.index,
                    y=ratio.values,
                    marker_color="#5F8D84",
                    hovertemplate="%{x|%b %d, %Y}<br>Vol / 30D: %{y:.2f}x<extra></extra>",
                )
            ]
        )
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#FBF8F1",
            plot_bgcolor="#FBF8F1",
            margin=dict(l=8, r=8, t=8, b=8),
            height=150,
            font=dict(
                family='"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                color="#1F271C",
                size=10,
            ),
            xaxis=dict(showgrid=False, tickfont=dict(color="#4F5A49")),
            yaxis=dict(
                showgrid=True, gridcolor="#D8D4C7", zeroline=False, tickfont=dict(color="#4F5A49")
            ),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)

    def _volume_multiple(self, snapshot: dict[str, float | None]) -> float:
        """Return the ratio of today's volume to the 30-day average, or 0.0 if unavailable."""
        current_volume = snapshot["current_volume"]
        average_volume = snapshot["average_volume"]
        if current_volume is None or average_volume in (None, 0.0):
            return 0.0
        return current_volume / average_volume

    def _liquidity_regime(self, vol_z: float | None) -> str:
        """Return a liquidity regime label ('HIGH ACTIVITY', 'NORMAL', or 'QUIET') from the volume z-score."""
        if vol_z is None:
            return "NORMAL"
        if vol_z > 2:
            return "HIGH ACTIVITY"
        if vol_z < -1:
            return "QUIET"
        return "NORMAL"

    def _duration_risk_color(self, value: float | None) -> str:
        """Return a hex color for the duration metric card: teal ≤3y, amber ≤7y, red otherwise."""
        if value is None:
            return "#1F271C"
        if value <= 3.0:
            return "#5F8D84"
        if value <= 7.0:
            return "#C9A64B"
        return "#A55C45"

    def _dv01_risk_color(self, value: float | None) -> str:
        """Return a hex color for the DV01 card: teal ≤$150/MM, amber ≤$500/MM, red otherwise."""
        if value is None:
            return "#1F271C"
        per_million = abs(value * 10000)
        if per_million <= 150:
            return "#5F8D84"
        if per_million <= 500:
            return "#C9A64B"
        return "#A55C45"

    def _cs_beta_risk_color(self, value: float | None) -> str:
        """Return a hex color for the CS beta card: teal ≤1 bp, amber ≤3 bp, red otherwise."""
        if value is None:
            return "#1F271C"
        beta_bps = abs(value * 10000)
        if beta_bps <= 1.0:
            return "#5F8D84"
        if beta_bps <= 3.0:
            return "#C9A64B"
        return "#A55C45"

    def _cs01_risk_color(self, value: float | None) -> str:
        """Return a hex color for the CS01 card: teal ≤$100/MM, amber ≤$400/MM, red otherwise."""
        if value is None:
            return "#1F271C"
        per_million = abs(value * 10000)
        if per_million <= 100:
            return "#5F8D84"
        if per_million <= 400:
            return "#C9A64B"
        return "#A55C45"

    def _r2_gauge(self, value: float | None) -> str:
        """Return an inline HTML progress bar representing the R² model fit quality."""
        if value is None:
            return ""
        pct = max(0.0, min(value, 1.0)) * 100.0
        return (
            f"<div style='margin-top:0.35rem;height:6px;background:rgba(111,123,70,0.12);border-radius:999px;'>"
            f"<div style='width:{pct:.1f}%;height:100%;border-radius:999px;background:linear-gradient(90deg, #5F8D84, #6F7B46);'></div>"
            "</div>"
        )

    def _dv01_change_footer(self, security: Security, duration: float | None) -> str | None:
        """Return a 30-day DV01 change label (e.g. '30d ↑ 2.3%'), or None if insufficient history."""
        if (
            duration is None
            or security.history.empty
            or "adj_close" not in security.history.columns
        ):
            return None
        prices = security.history["adj_close"].astype(float).dropna()
        if len(prices) < 31:
            return None
        current = duration * float(prices.iloc[-1])
        prior = duration * float(prices.iloc[-31])
        if prior == 0:
            return None
        pct = ((current / prior) - 1.0) * 100.0
        arrow = "↑" if pct > 0 else "↓" if pct < 0 else "→"
        return f"30d {arrow} {abs(pct):.1f}%"

    def _duration_scale_indicator(self, duration: float | None) -> str | None:
        """Return an inline HTML scale bar with a dot marker positioned on a 0–30Y axis."""
        if duration is None:
            return None
        scale_max = 30.0
        pct = max(0.0, min(duration / scale_max, 1.0)) * 100.0
        return (
            "<div style='display:flex;align-items:center;gap:0.45rem;'>"
            "<span>0Y</span>"
            f"<div style='position:relative;flex:1;height:4px;background:rgba(111,123,70,0.12);border-radius:999px;'>"
            f"<div style='position:absolute;left:calc({pct:.1f}% - 5px);top:-3px;width:10px;height:10px;border-radius:50%;background:#5F8D84;'></div>"
            "</div>"
            "<span>30Y</span>"
            "</div>"
        )
