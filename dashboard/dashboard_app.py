import streamlit as st

from config import APP_ENV, normalize_asset_class
from dashboard.components import DashboardControls, SecurityHeader
from dashboard.home_page import HomePage
from dashboard.news_page import NewsPage
from dashboard.styles import apply_dashboard_theme
from dashboard.tabs import AnalyticsTab, GraphsTab, MacroTab, RVTab
from repositories.macro import MacroFeatureRepository
from repositories.market import InputRepository, MetadataRepository, PriceRepository, SecurityRepository
from db.connection import get_engine
from models.security import Security


class DashboardApp:
    """Coordinate the Streamlit ETF dashboard and wire repositories into the UI."""

    def __init__(self, security_repo, price_repo, input_repo, metadata_repo, macro_feature_repo):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.input_repo = input_repo
        self.metadata_repo = metadata_repo
        self.macro_feature_repo = macro_feature_repo
        self.home_page = HomePage(price_repo)
        self.news_page = NewsPage()
        self.macro_tab = MacroTab(macro_feature_repo)
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

        if "active_view" not in st.session_state:
            st.session_state["active_view"] = "Home"

        nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.columns([1, 1, 1, 1, 3], vertical_alignment="center")
        with nav_col1:
            if st.button("Home", key="nav_home", use_container_width=True):
                st.session_state["active_view"] = "Home"
                st.rerun()
        with nav_col2:
            if st.button("Dashboard", key="nav_dashboard", use_container_width=True):
                st.session_state["active_view"] = "Dashboard"
                st.rerun()
        with nav_col3:
            if st.button("News", key="nav_news", use_container_width=True):
                st.session_state["active_view"] = "News"
                st.rerun()
        with nav_col4:
            if st.button("Macro", key="nav_macro", use_container_width=True):
                st.session_state["active_view"] = "Macro"
                st.rerun()
        with nav_col5:
            st.caption(
                f"Current View: {st.session_state['active_view']} | Environment: {APP_ENV.upper()}"
            )

        if st.session_state["active_view"] == "Home":
            self.home_page.render(securities)
            return

        if st.session_state["active_view"] == "News":
            self.news_page.render()
            return

        if st.session_state["active_view"] == "Macro":
            self.macro_tab.render()
            return

        self._render_dashboard(securities)

    def _render_dashboard(self, securities):
        """Render the analytical dashboard workspace after the home page entry point."""

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
    macro_feature_repo = MacroFeatureRepository(engine)

    app = DashboardApp(security_repo, price_repo, input_repo, metadata_repo, macro_feature_repo)
    app.run()
