"""Overview tab: date-windowed price and volume charts with a raw history expander."""

import streamlit as st

from dashboard.components.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)
from dashboard.components.controls import DashboardControls
from dashboard.components.info_panel import InfoPanel
from dashboard.styles.table_styles import DashboardTable
from fixed_income.instruments.security import Security


class OverviewTab:
    """Render price and volume charts plus the raw history table."""

    def __init__(self) -> None:
        self.table = DashboardTable()
        self.controls = DashboardControls()
        self.info_panel = InfoPanel()

    def _render_section_label(self, title: str, subtitle: str, *, accent_color: str) -> None:
        """Render a small section heading with an accented uppercase title and a muted subtitle."""
        st.markdown(
            (
                "<div style='margin-top:0.25rem;margin-bottom:0.25rem;'>"
                f"<div style='color:{accent_color};font-size:0.76rem;font-weight:700;"
                "text-transform:uppercase;letter-spacing:0.45px;'>"
                f"{title}</div>"
                "<div style='color:#8F8A80;font-size:0.78rem;line-height:1.35;'>"
                f"{subtitle}</div></div>"
            ),
            unsafe_allow_html=True,
        )

    def render(self, security: Security) -> None:
        """Render the Overview tab: window summary note, price chart, volume chart, and history expander."""
        st.subheader("Overview")

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

        filtered_hist = security.history_between(start_date, end_date)
        latest_close = float(filtered_hist["close"].iloc[-1])
        observations = len(filtered_hist)
        average_volume = float(filtered_hist["volume"].mean())

        self.info_panel.render_note(
            "Window Summary",
            (
                f"{selected_security} | {start_date.date()} to {end_date.date()} | "
                f"{observations} observations | Latest close {latest_close:.2f} | "
                f"Average volume {average_volume:,.0f}"
            ),
            accent_color="#5F8D84",
            margin_top="0.15rem",
            margin_bottom="0.50rem",
        )

        self._render_section_label(
            "Price Action",
            "Spot price versus recent mean and one-standard-deviation range.",
            accent_color="#6F7B46",
        )
        render_price_chart(hist, selected_security, start_date, end_date)

        self._render_section_label(
            "Participation",
            "Observed trading volume with the selected-window average for context.",
            accent_color="#5F8D84",
        )
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
