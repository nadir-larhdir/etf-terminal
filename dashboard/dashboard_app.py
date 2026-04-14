import streamlit as st

from config import APP_ENV, DATA_BACKEND
from dashboard.cache import app_cache_key, cached_active_securities
from dashboard.pages import DashboardPage, HomePage, MacroPage, NewsPage
from dashboard.perf import timed_block
from dashboard.styles import apply_dashboard_theme
from fixed_income.analytics import DurationModelSelector, FixedIncomeAnalyticsService
from stores.macro import MacroFeatureStore, MacroStore
from stores.analytics import AnalyticsSnapshotStore
from stores.market import MetadataStore, PriceStore, SecurityStore
from db.connection import get_engine


NAVIGATION_VIEWS = ("Home", "Dashboard", "News", "Macro")


@st.cache_resource(show_spinner=False)
def get_cached_app_dependencies(data_backend: str, app_env: str):
    engine = get_engine(data_backend=data_backend, app_env=app_env)
    price_store = PriceStore(engine)
    macro_store = MacroStore(engine)
    duration_selector = DurationModelSelector()
    analytics_snapshot_store = AnalyticsSnapshotStore(engine)
    return {
        "engine": engine,
        "security_store": SecurityStore(engine),
        "price_store": price_store,
        "metadata_store": MetadataStore(engine),
        "macro_store": macro_store,
        "macro_feature_store": MacroFeatureStore(engine),
        "analytics_snapshot_store": analytics_snapshot_store,
        "duration_selector": duration_selector,
        "analytics_service": FixedIncomeAnalyticsService(price_store, macro_store, duration_selector, analytics_snapshot_store),
    }


class DashboardApp:
    """Coordinate the Streamlit ETF dashboard and wire data stores into the UI."""

    def __init__(
        self,
        security_store,
        price_store,
        metadata_store,
        macro_store,
        macro_feature_store,
        analytics_service,
    ):
        self.security_store = security_store
        self.price_store = price_store
        self.metadata_store = metadata_store
        self.macro_store = macro_store
        self.macro_feature_store = macro_feature_store
        self.home_page = HomePage(price_store)
        self.news_page = NewsPage(macro_feature_store)
        self.dashboard_page = DashboardPage(price_store, metadata_store, analytics_service)
        self.macro_page = MacroPage(macro_feature_store)

    def run(self):
        apply_dashboard_theme()
        st.title("ETF Terminal")
        st.caption("Fixed income ETF analytics terminal for market structure, liquidity, and relative value monitoring.")

        cache_key = app_cache_key(self.security_store.engine)
        with timed_block("dashboard.load_active_securities"):
            securities = cached_active_securities(cache_key, self.security_store)
        if securities.empty or "ticker" not in securities.columns:
            st.warning("No active securities found in the database.")
            return

        if "active_view" not in st.session_state:
            st.session_state["active_view"] = "Home"

        self._render_navigation()

        if st.session_state["active_view"] == "Home":
            self._render_tab_safe("Home", self.home_page.render, securities)
            return

        if st.session_state["active_view"] == "News":
            self._render_tab_safe("News", self.news_page.render)
            return

        if st.session_state["active_view"] == "Macro":
            self._render_tab_safe("Macro", self.macro_page.render)
            return

        self._render_tab_safe("Dashboard", self.dashboard_page.render, securities, self._render_tab_safe)

    def _render_navigation(self) -> None:
        nav_columns = st.columns([1, 1, 1, 1, 3], vertical_alignment="center")
        for column, view_name in zip(nav_columns[:4], NAVIGATION_VIEWS, strict=False):
            with column:
                if st.button(view_name, key=f"nav_{view_name.lower()}", use_container_width=True):
                    st.session_state["active_view"] = view_name
                    st.rerun()

        with nav_columns[4]:
            st.caption(
                f"Current View: {st.session_state['active_view']} | Environment: {APP_ENV.upper()} | Backend: {DATA_BACKEND.upper()}"
            )

    def _render_tab_safe(self, tab_name: str, render_fn, *args) -> None:
        try:
            render_fn(*args)
        except Exception as exc:
            st.error(f"{tab_name} failed to render: {exc}")


def run_app():
    """Create the application dependencies and launch the Streamlit dashboard."""

    dependencies = get_cached_app_dependencies(DATA_BACKEND, APP_ENV)

    app = DashboardApp(
        dependencies["security_store"],
        dependencies["price_store"],
        dependencies["metadata_store"],
        dependencies["macro_store"],
        dependencies["macro_feature_store"],
        dependencies["analytics_service"],
    )
    app.run()
