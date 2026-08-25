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
from dashboard.format import Formatter
from dashboard.mobile import PLOTLY_CHART_CONFIG
from dashboard.perf import timed_block
from dashboard.presenters.analytics import AnalyticsPresenter, DurationScale, Gauge, MetricCard
from dashboard.render import render, stylesheet
from fixed_income.analytics.duration_estimator import duration_source_details
from fixed_income.etfs import ETF
from fixed_income.series import VOLUME_WINDOW

FMT = Formatter()
LOGGER = logging.getLogger(__name__)


class AnalyticsTab:
    """Display model-based ETF rate-risk and trading diagnostics."""

    def __init__(self, analytics_service) -> None:
        self.analytics_service = analytics_service
        self.presenter = AnalyticsPresenter()

    def render(self, security: ETF) -> None:
        """Render the Analytics tab: metric cards and credit spread diagnostics."""
        st.subheader("Analytics")
        self.render_metric_cards(security)

    def render_metric_cards(self, security: ETF) -> None:
        """Render the instrument, rate-risk, and credit-spread metric card rows."""
        st.markdown(stylesheet("analytics_tab.css"), unsafe_allow_html=True)
        with timed_block("analytics.prepare_inputs"):
            analytics = self._analytics_snapshot(security)
            duration_method, duration_source = duration_source_details(security.ticker)
            duration_scale = DurationScale.from_years(analytics.estimated_duration)
            cards = [
                self.presenter.instrument_cards(security),
                self.presenter.rate_risk_cards(
                    analytics,
                    duration_method=duration_method,
                    duration_source=duration_source,
                    duration_footer=(
                        None
                        if duration_scale is None
                        else render("analytics/duration_scale.html", scale=duration_scale)
                    ),
                    dv01_footer=self.presenter.dv01_change_footer(
                        security, analytics.estimated_duration
                    ),
                ),
            ]

        for row in cards:
            self._render_card_row(row)

        spread_cards = self.presenter.spread_risk_cards(analytics)
        if not spread_cards:
            return
        st.markdown(render("analytics/section_divider.html"), unsafe_allow_html=True)
        self._render_card_row(spread_cards, fit_footer_for=analytics)

    def _render_card_row(self, cards: list[MetricCard], *, fit_footer_for=None) -> None:
        """Lay one row of metric cards across equal columns."""
        for column, card in zip(st.columns(len(cards)), cards, strict=True):
            footer = card.footer
            if fit_footer_for is not None and card.label == "Credit Spread R²":
                footer = render(
                    "analytics/fit_footer.html",
                    gauge=Gauge.from_fraction(fit_footer_for.spread_model_r2),
                    observations=fit_footer_for.observations_used or "N/A",
                )
            with column:
                st.markdown(
                    render("analytics/metric_card.html", card=card, footer=footer),
                    unsafe_allow_html=True,
                )

    def render_narrative_panels(self, security: ETF) -> None:
        """Render the Current Read and Liquidity Condition panels side by side."""
        with timed_block("analytics.narrative_panels"):
            analytics = self._analytics_snapshot(security)
            snapshot = security.trading_snapshot()
            duration_method, duration_source = duration_source_details(security.ticker)

        left, right = st.columns([3, 2])
        with left:
            with st.container(border=True):
                st.markdown(
                    render(
                        "analytics/read_panel.html",
                        kicker="Current Read",
                        headline=self.presenter.read_headline(security),
                        body=self.presenter.read_body(
                            security,
                            analytics,
                            duration_method=duration_method,
                            duration_source=duration_source,
                        ),
                    ),
                    unsafe_allow_html=True,
                )
        with right:
            with st.container(border=True):
                st.markdown(
                    render(
                        "analytics/read_panel.html",
                        kicker="Liquidity Condition",
                        headline=self.presenter.liquidity_regime(snapshot["volume_z"]),
                        body=self.presenter.liquidity_summary(security),
                    ),
                    unsafe_allow_html=True,
                )
                self._render_volume_bars(security, show_caption=False, height=110)

    def _analytics_snapshot(self, security: ETF):
        """Return a live or cached analytics snapshot, falling back to live computation when stale."""
        cache_key = app_cache_key(self.analytics_service.price_store.engine)
        price_as_of = (
            pd.Timestamp(security.history.index.max()).date().isoformat()
            if not security.history.empty
            else "n/a"
        )
        metadata_duration = security.metadata_number("duration")
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

    def _render_volume_bars(
        self, security: ETF, *, show_caption: bool = True, height: int = 150
    ) -> None:
        """Render a 30-day bar chart of volume relative to the rolling 30D average."""
        history = security.history.copy()
        if history.empty or "volume" not in history.columns:
            return
        volume = history["volume"].astype(float)
        ratio = (volume / VOLUME_WINDOW.mean(volume)).dropna().tail(30)
        if ratio.empty:
            return
        if show_caption:
            st.caption("Volume vs 30D average")
        fig = go.Figure(
            data=[
                go.Bar(
                    x=ratio.index,
                    y=ratio.values,
                    marker_color="#7FB9AA",
                    hovertemplate="%{x|%b %d, %Y}<br>Vol / 30D: %{y:.2f}x<extra></extra>",
                )
            ]
        )
        fig.update_layout(
            template="plotly_white",
            paper_bgcolor="#FBF8F1",
            plot_bgcolor="#FBF8F1",
            margin=dict(l=8, r=8, t=8, b=8),
            height=height,
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
