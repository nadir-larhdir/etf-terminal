import streamlit as st

from dashboard.components.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)
from dashboard.components.controls import DashboardControls
from dashboard.styles.table_styles import DashboardTable
from models.security import Security


class GraphsTab:
    """Render price and volume charts plus the raw history table."""

    def __init__(self) -> None:
        self.table = DashboardTable()
        self.controls = DashboardControls()

    def render(self, security: Security) -> None:
        st.subheader("Charts")

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

        st.caption(f"Displaying {selected_security} from {start_date.date()} to {end_date.date()}")

        render_price_chart(hist, selected_security, start_date, end_date)
        render_volume_chart(hist, selected_security, start_date, end_date)

        with st.expander(f"Show {selected_security} raw price history"):
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
