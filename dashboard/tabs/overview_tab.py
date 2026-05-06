"""Overview tab: analytics metric cards and date-windowed price and volume charts."""

import streamlit as st

from dashboard.components.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)
from dashboard.components.controls import DashboardControls
from dashboard.styles.table_styles import DashboardTable
from fixed_income.etfs import ETF


class OverviewTab:
    """Render analytics metric cards plus price and volume charts."""

    def __init__(self, analytics_tab) -> None:
        self.analytics_tab = analytics_tab
        self.table = DashboardTable()
        self.controls = DashboardControls()

    def render(self, security: ETF) -> None:
        """Render the Overview tab: analytics cards, chart window controls, and charts."""
        st.subheader("Overview")

        self.analytics_tab.render_metric_cards(security)

        st.markdown("<div class='ov-divider'></div>", unsafe_allow_html=True)

        hist = security.history
        selected_security = security.ticker

        default_period = "6M"
        default_start, default_end = compute_default_date_range(hist, default_period)

        _, start_date, end_date = self.controls.render_window_and_dates(
            window_label="Preset Window",
            window_options=["5D", "30D", "3M", "6M", "1Y", "ALL"],
            window_index=3,
            window_key=f"graphs_period_{selected_security}",
            start_label="Start Date",
            end_label="End Date",
            default_start=default_start,
            default_end=default_end,
            min_date=hist.index.min().date(),
            max_date=hist.index.max().date(),
            start_key=f"start_{selected_security}_{default_period}",
            end_key=f"end_{selected_security}_{default_period}",
        )

        price_col, volume_col = st.columns(2)
        with price_col:
            render_price_chart(hist, selected_security, start_date, end_date)

        with volume_col:
            render_volume_chart(hist, selected_security, start_date, end_date)

        with st.expander(f"{selected_security} Recent Price History"):
            st.caption("Last 20 observations from the stored time series.")

            display_hist = hist.tail(20).copy().reset_index()
            display_hist = display_hist.rename(columns={"index": "date"})
            display_hist = self.table.format_history(display_hist)
            display_hist = display_hist.rename(
                columns={
                    "date": "DATE",
                    "open": "OPEN",
                    "high": "HIGH",
                    "low": "LOW",
                    "close": "CLOSE",
                    "adj_close": "ADJ CLOSE",
                    "volume": "VOLUME",
                }
            )
            self.table.render(display_hist, hide_index=True)
