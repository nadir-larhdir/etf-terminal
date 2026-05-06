"""Dashboard page: universe filter, ETF selector, left panel, and tabbed analytics workspace."""

import pandas as pd
import streamlit as st

from config import normalize_asset_class
from dashboard.cache import app_cache_key, cached_etf_metadata, cached_price_history
from dashboard.components import DashboardControls
from dashboard.perf import timed_block
from dashboard.tabs import AnalyticsTab, HoldingsTab, OverviewTab, RVTab
from fixed_income.etfs import ETF

_PANEL_CSS = """
<style>
[class^="db-"], [class^="db-"] * {
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
.db-price-card {
    border: 1px solid var(--etf-border);
    background: var(--etf-bg-elevated);
    padding: 0.55rem 0.65rem 0.50rem 0.65rem;
    margin: 0.35rem 0 0.40rem 0;
}
.db-price-ticker {
    color: var(--etf-ink-muted);
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.42px;
    margin-bottom: 0.04rem;
}
.db-price-value {
    color: var(--etf-ink);
    font-size: 1.80rem;
    font-weight: 700;
    line-height: 1.04;
    margin-bottom: 0.12rem;
    letter-spacing: -0.3px;
}
.db-price-chg-row {
    display: flex;
    gap: 0.55rem;
    align-items: baseline;
}
.db-price-chg { font-size: 0.86rem; font-weight: 700; }
.db-price-pos { color: var(--etf-up); }
.db-price-neg { color: var(--etf-down); }
.db-meta-list {
    margin: 0 0 0.40rem 0;
    border: 1px solid var(--etf-border);
    background: var(--etf-bg-panel);
}
.db-meta-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.17rem 0.50rem;
    border-bottom: 1px solid var(--etf-border);
    gap: 0.3rem;
}
.db-meta-row:last-child { border-bottom: none; }
.db-meta-key {
    color: var(--etf-ink-muted);
    font-size: 0.60rem;
    text-transform: uppercase;
    letter-spacing: 0.28px;
    flex-shrink: 0;
}
.db-meta-val {
    color: var(--etf-ink);
    font-size: 0.65rem;
    font-weight: 600;
    text-align: right;
    word-break: break-word;
}
.db-nav-label {
    color: var(--etf-ink-muted);
    font-size: 0.60rem;
    text-transform: uppercase;
    letter-spacing: 0.42px;
    margin: 0.40rem 0 0.10rem 0;
    font-weight: 700;
}
.db-nav-stack {
    display: grid;
    gap: 0.08rem;
    align-items: start;
    justify-items: center;
}
.st-key-db_tab_overview button,
.st-key-db_tab_holdings button,
.st-key-db_tab_rv button {
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    display: block !important;
    box-shadow: none !important;
    color: var(--etf-ink-muted) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    padding: 0.26rem 0.55rem !important;
    border-radius: 0 !important;
    width: auto !important;
    min-height: 2.05rem !important;
    height: 2.05rem !important;
    line-height: 1 !important;
    text-align: center !important;
    justify-content: center !important;
    margin: 0 auto !important;
    cursor: pointer !important;
    text-transform: uppercase !important;
    letter-spacing: 0.38px !important;
}
.st-key-db_tab_overview button:hover,
.st-key-db_tab_holdings button:hover,
.st-key-db_tab_rv button:hover {
    background: rgba(111,123,70,0.06) !important;
    color: var(--etf-ink) !important;
    border-bottom-color: var(--etf-border-strong) !important;
}
.st-key-db_tab_overview button[kind="primary"],
.st-key-db_tab_holdings button[kind="primary"],
.st-key-db_tab_rv button[kind="primary"] {
    color: var(--etf-accent) !important;
    font-weight: 600 !important;
    background: transparent !important;
    border-bottom-color: var(--etf-accent) !important;
}
</style>
"""

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

    def _format_aum(self, value) -> str:
        """Format AUM to compact string (1.2B, 450M, etc.)."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "N/A"
        if v >= 1_000_000_000:
            return f"{v / 1_000_000_000:.1f}B"
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v / 1_000:.1f}K"
        return f"{v:,.0f}"

    def _render_price_card(self, hist, selected_etf: str) -> None:
        """Render the large price card: ticker, PX_LAST, CHG, CHG%."""
        px_last = float(hist["close"].iloc[-1])
        prev_close = float(hist["close"].iloc[-2]) if len(hist) > 1 else px_last
        chg = px_last - prev_close
        chg_pct = (chg / prev_close * 100) if prev_close != 0 else 0.0
        chg_class = "db-price-pos" if chg >= 0 else "db-price-neg"
        sign = "+" if chg >= 0 else ""
        st.markdown(
            f"<div class='db-price-card'>"
            f"<div class='db-price-ticker'>{selected_etf} · PX_LAST</div>"
            f"<div class='db-price-value'>{px_last:,.2f}</div>"
            f"<div class='db-price-chg-row'>"
            f"<span class='db-price-chg {chg_class}'>{sign}{chg:,.2f}</span>"
            f"<span class='db-price-chg {chg_class}'>{sign}{chg_pct:.2f}%</span>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    def _format_percent(self, value) -> str:
        """Format a numeric percent value like 4.37 -> 4.37%."""
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return "N/A"

    def _volume_multiple(self, hist) -> str:
        """Format latest volume versus 30-day average as xN.NN."""
        if hist.empty or "volume" not in hist.columns:
            return "N/A"
        volume = hist["volume"].astype(float)
        average = volume.rolling(30, min_periods=5).mean().iloc[-1]
        current = volume.iloc[-1]
        if pd.isna(current) or pd.isna(average) or average == 0:
            return "N/A"
        return f"x{current / average:.2f}"

    def _render_metadata_panel(self, metadata: dict, hist) -> None:
        """Render the key-value metadata list below the price card."""

        def _v(key: str) -> str:
            val = metadata.get(key)
            return str(val) if val else "N/A"

        exp_ratio = metadata.get("expense_ratio")
        try:
            exp_ratio_str = f"{float(exp_ratio):.2f}%"
        except (TypeError, ValueError):
            exp_ratio_str = "N/A"

        rows = [
            ("Category", _v("category")),
            ("Benchmark", _v("benchmark_index")),
            ("Duration", _v("duration_bucket")),
            ("Issuer", _v("issuer")),
            ("YTM", self._format_percent(metadata.get("yield_to_maturity"))),
            ("Liquidity", self._volume_multiple(hist)),
            ("AUM", self._format_aum(metadata.get("total_assets"))),
            ("Exp Ratio", exp_ratio_str),
        ]
        cells = "".join(
            f"<div class='db-meta-row'>"
            f"<span class='db-meta-key'>{k}</span>"
            f"<span class='db-meta-val'>{v}</span>"
            f"</div>"
            for k, v in rows
        )
        st.markdown(f"<div class='db-meta-list'>{cells}</div>", unsafe_allow_html=True)

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
        st.markdown(_PANEL_CSS, unsafe_allow_html=True)

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

            self._render_price_card(hist, selected_etf)
            self._render_metadata_panel(metadata, hist)

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
