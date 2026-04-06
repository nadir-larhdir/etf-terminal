import streamlit as st

from config import normalize_asset_class
from dashboard.components import DashboardControls, SecurityHeader
from dashboard.perf import timed_block
from dashboard.tabs import AnalyticsTab, OverviewTab, RVTab
from fixed_income.instruments.security import Security


class DashboardPage:
    """Render the main ETF workspace page behind the Dashboard navigation view."""

    def __init__(self, price_store, metadata_store, analytics_service) -> None:
        self.price_store = price_store
        self.metadata_store = metadata_store
        self.security_header = SecurityHeader()
        self.overview_tab = OverviewTab()
        self.analytics_tab = AnalyticsTab(analytics_service)
        self.rv_tab = RVTab(price_store)
        self.controls = DashboardControls()

    def render(self, securities, render_tab_safe) -> None:
        if "asset_class" not in securities.columns:
            securities["asset_class"] = "Other"
        securities["asset_class"] = securities["asset_class"].fillna("Other").map(normalize_asset_class)

        asset_classes = sorted([asset for asset in securities["asset_class"].dropna().unique().tolist() if asset])
        universe_options = ["All"] + asset_classes

        filter_col, selector_col, desc_col = st.columns([0.7, 0.9, 2.4])

        with filter_col:
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
        filtered_securities = filtered_securities.sort_values(["asset_class", "ticker"]).reset_index(drop=True)
        ticker_options = filtered_securities["ticker"].tolist()

        if not ticker_options:
            st.warning("No securities available for the selected universe.")
            return

        with selector_col:
            selected_security = self.controls.render_security_select(
                "Security",
                filtered_securities,
                key="main_security_selector",
            )

        selected_row = filtered_securities.loc[filtered_securities["ticker"] == selected_security].iloc[0]
        security = Security(
            selected_security,
            name=selected_row.get("name"),
            asset_class=selected_row.get("asset_class"),
        )
        with timed_block("dashboard.load_metadata"):
            metadata = security.load_metadata(self.metadata_store)

        with desc_col:
            self.security_header.render_description(securities, selected_security, metadata)

        with timed_block("dashboard.load_price_history"):
            hist = security.load_history(self.price_store)

        if hist.empty:
            st.warning(f"No price history found for {selected_security}.")
            return

        self.security_header.render_header_strip(hist, selected_security, metadata)

        all_tickers = securities["ticker"].tolist()
        tab_overview, tab_analytics, tab_rv = st.tabs(["Overview", "Analytics", "RV Analysis"])

        with tab_overview:
            render_tab_safe("Overview", self.overview_tab.render, security)

        with tab_analytics:
            render_tab_safe("Analytics", self.analytics_tab.render, security)

        with tab_rv:
            render_tab_safe("RV Analysis", self.rv_tab.render, security, all_tickers)
