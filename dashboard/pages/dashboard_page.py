"""Dashboard page: universe filter, ETF selector, left panel, and tabbed analytics workspace."""

import streamlit as st

from config import normalize_asset_class
from dashboard.cache import app_cache_key, cached_etf_metadata, cached_price_history
from dashboard.components import DashboardControls
from dashboard.perf import timed_block
from dashboard.presenters.security import PriceCard, metadata_rows
from dashboard.render import render, stylesheet
from dashboard.tabs import AnalyticsTab, HoldingsTab, OverviewTab, RVTab
from fixed_income.etfs import ETF

_TAB_KEYS = {
    "Overview": "overview",
    "Holdings": "holdings",
    "RV Analysis": "rv",
}


class DashboardPage:
    """Render the main ETF workspace page behind the Dashboard navigation view."""

    def __init__(self, price_store, metadata_store, analytics_service, holdings_store) -> None:
        self.price_store = price_store
        self.metadata_store = metadata_store
        analytics_tab = AnalyticsTab(analytics_service)
        self.overview_tab = OverviewTab(analytics_tab)
        self.holdings_tab = HoldingsTab(holdings_store)
        self.rv_tab = RVTab(price_store)
        self.controls = DashboardControls()

    def _render_security_panel(self, ticker: str, metadata: dict, hist) -> None:
        """Render the price card and metadata list for the selected ETF."""
        card = PriceCard.from_history(ticker, hist)
        if card is not None:
            st.markdown(render("security/price_card.html", card=card), unsafe_allow_html=True)
        st.markdown(
            render("security/metadata_panel.html", rows=metadata_rows(metadata, hist)),
            unsafe_allow_html=True,
        )

    def _render_nav_tabs(self, active_tab: str) -> str | None:
        """Render vertical sub-tab navigation buttons; return clicked tab name or None."""
        st.markdown("<div class='db-nav-label'>View</div>", unsafe_allow_html=True)
        st.markdown("<div class='db-nav-stack'>", unsafe_allow_html=True)
        clicked = None
        for tab, key in _TAB_KEYS.items():
            with st.container(key=f"db_tab_{key}"):
                if st.button(
                    tab,
                    key=f"nav_{key}",
                    use_container_width=True,
                    type="primary" if tab == active_tab else "secondary",
                ):
                    clicked = tab
        st.markdown("</div>", unsafe_allow_html=True)
        return clicked

    def render(self, securities, render_tab_safe) -> None:
        """Render the full dashboard page with left panel and content area."""
        st.markdown(stylesheet("dashboard_panel.css"), unsafe_allow_html=True)

        if "asset_class" not in securities.columns:
            securities["asset_class"] = "Other"
        securities["asset_class"] = (
            securities["asset_class"].fillna("Other").map(normalize_asset_class)
        )

        asset_classes = sorted(
            [a for a in securities["asset_class"].dropna().unique().tolist() if a]
        )
        universe_options = ["All"] + asset_classes
        all_tickers = securities["ticker"].tolist()

        valid_tabs = set(_TAB_KEYS.keys())
        if st.session_state.get("dashboard_active_tab") not in valid_tabs:
            st.session_state["dashboard_active_tab"] = "Overview"

        left_col, right_col = st.columns([1, 3.5])

        with left_col:
            selected_universe = self.controls.render_select(
                "Universe",
                universe_options,
                key="main_security_universe",
            )
            filtered_securities = (
                securities.copy()
                if selected_universe == "All"
                else securities.loc[securities["asset_class"] == selected_universe].copy()
            )
            filtered_securities = filtered_securities.sort_values(
                ["asset_class", "ticker"]
            ).reset_index(drop=True)

            if filtered_securities.empty:
                st.warning("No ETFs for the selected universe.")
                return

            selected_etf = self.controls.render_etf_select(
                "ETF",
                filtered_securities,
                key="main_security_selector",
            )
            if not selected_etf:
                return

            selected_row = filtered_securities.loc[
                filtered_securities["ticker"] == selected_etf
            ].iloc[0]
            etf = ETF(
                selected_etf,
                name=selected_row.get("name"),
                asset_class=selected_row.get("asset_class"),
            )
            cache_key = app_cache_key(self.price_store.engine)
            with timed_block("dashboard.load_metadata"):
                metadata = cached_etf_metadata(cache_key, selected_etf, self.metadata_store) or {}
                etf.set_metadata(metadata)

            with timed_block("dashboard.load_price_history"):
                hist = cached_price_history(cache_key, selected_etf, None, None, self.price_store)
                etf.set_history(hist)

            if hist.empty:
                st.warning(f"No price history for {selected_etf}.")
                return

            self._render_security_panel(selected_etf, metadata, hist)

            clicked_tab = self._render_nav_tabs(st.session_state["dashboard_active_tab"])
            if clicked_tab:
                st.session_state["dashboard_active_tab"] = clicked_tab
                st.rerun()

        with right_col:
            active_section = st.session_state["dashboard_active_tab"]

            if active_section == "Overview":
                render_tab_safe("Overview", self.overview_tab.render, etf)
            elif active_section == "Holdings":
                render_tab_safe("Holdings", self.holdings_tab.render, etf)
            else:
                render_tab_safe("RV Analysis", self.rv_tab.render, etf, all_tickers)
