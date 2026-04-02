import streamlit as st

from dashboard.components import DashboardControls, SecurityHeader
from dashboard.styles import apply_dashboard_theme
from dashboard.tabs import AnalyticsTab, GraphsTab, RVTab
from repositories.market import InputRepository, MetadataRepository, PriceRepository, SecurityRepository
from db.connection import get_engine
from models.security import Security


class DashboardApp:
    """Coordinate the Streamlit ETF dashboard and wire repositories into the UI."""

    def __init__(self, security_repo, price_repo, input_repo, metadata_repo):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.input_repo = input_repo
        self.metadata_repo = metadata_repo
        self.security_header = SecurityHeader()
        self.graphs_tab = GraphsTab()
        self.analytics_tab = AnalyticsTab()
        self.rv_tab = RVTab(price_repo)
        self.controls = DashboardControls()

    def run(self):
        apply_dashboard_theme()
        st.title("ETF Terminal")
        st.caption("Fixed income ETF analytics terminal for market structure, liquidity, and relative value monitoring.")

        securities = self.security_repo.list_active_securities().copy()
        if securities.empty or "ticker" not in securities.columns:
            st.warning("No active securities found in the database.")
            return

        if "asset_class" not in securities.columns:
            securities["asset_class"] = "Other"
        securities["asset_class"] = securities["asset_class"].fillna("Other")

        asset_classes = sorted([asset for asset in securities["asset_class"].dropna().unique().tolist() if asset])
        universe_options = ["All"] + asset_classes

        filter_col, selector_col, desc_col = st.columns([0.7, 0.9, 2.4])

        with filter_col:
            selected_universe = self.controls.render_select(
                "Universe",
                universe_options,
                key="main_security_universe",
            )

        if selected_universe == "All":
            filtered_securities = securities.copy()
        else:
            filtered_securities = securities.loc[securities["asset_class"] == selected_universe].copy()

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

        security = Security(selected_security)
        metadata = security.load_metadata(self.metadata_repo)

        with desc_col:
            self.security_header.render_description(securities, selected_security, metadata)

        hist = security.load_history(self.price_repo)

        if hist.empty:
            st.warning(f"No price history found for {selected_security}.")
            return

        self.security_header.render_header_strip(hist, selected_security)

        all_tickers = securities["ticker"].tolist()
        tab_graphs, tab_analytics, tab_rv = st.tabs(["Graphs", "Analytics", "RV Analysis"])

        with tab_graphs:
            self.graphs_tab.render(security)

        with tab_analytics:
            self.analytics_tab.render(security)

        with tab_rv:
            self.rv_tab.render(security, all_tickers)


def run_app():
    """Create the application dependencies and launch the Streamlit dashboard."""

    engine = get_engine()
    security_repo = SecurityRepository(engine)
    price_repo = PriceRepository(engine)
    input_repo = InputRepository(engine)
    metadata_repo = MetadataRepository(engine)

    app = DashboardApp(security_repo, price_repo, input_repo, metadata_repo)
    app.run()
