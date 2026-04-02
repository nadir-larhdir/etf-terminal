import streamlit as st

from dashboard.styles import apply_bloomberg_theme
from dashboard.header_panel import HeaderPanel
from dashboard.graphs_tab import GraphsTab
from dashboard.analytics_tab import AnalyticsTab
from dashboard.rv_tab import RVTab
from dashboard.controls import BloombergControls


class Dashboard:
    def __init__(self, security_repo, price_repo, input_repo, metadata_repo):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.input_repo = input_repo
        self.metadata_repo = metadata_repo
        self.header_panel = HeaderPanel()
        self.graphs_tab = GraphsTab()
        self.analytics_tab = AnalyticsTab()
        self.rv_tab = RVTab(price_repo)
        self.controls = BloombergControls()


    def run(self):
        apply_bloomberg_theme()
        st.title("ETF MONITOR")
        st.caption("Database-backed ETF dashboard")

        securities = self.security_repo.get_all()
        tickers = securities["ticker"].tolist()

        if not tickers:
            st.warning("No active securities found in the database.")
            return

        selector_col, desc_col = st.columns([0.7, 2.7])

        with selector_col:
            selected_security = self.controls.render_select(
                "Security",
                tickers,
                key="main_security_selector",
            )

        metadata = self.metadata_repo.get_metadata(selected_security)

        with desc_col:
            self.header_panel.render_description(securities, selected_security, metadata)

        hist = self.price_repo.get_price_history(selected_security)

        if hist.empty:
            st.warning(f"No price history found for {selected_security}.")
            return

        self.header_panel.render_header_strip(hist, selected_security)

        tab_graphs, tab_analytics, tab_rv = st.tabs(["Graphs", "Analytics", "RV Analysis"])

        with tab_graphs:
            self.graphs_tab.render(hist, selected_security)

        with tab_analytics:
            self.analytics_tab.render(hist)

        with tab_rv:
            self.rv_tab.render(hist, tickers, selected_security)