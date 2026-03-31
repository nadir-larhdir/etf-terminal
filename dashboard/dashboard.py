import streamlit as st
from dashboard.styles import apply_bloomberg_theme

from dashboard.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)


class Dashboard:
    def __init__(self, security_repo, price_repo, input_repo):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.input_repo = input_repo

    def run(self):
        apply_bloomberg_theme()
        st.title("ETF MONITOR")
        st.caption("Database-backed ETF dashboard")

        securities = self.security_repo.get_all()
        tickers = securities["ticker"].tolist()

        if not tickers:
            st.warning("No active securities found in the database.")
            return

        selected_security = st.selectbox("Security", tickers)
        hist = self.price_repo.get_price_history(selected_security)

        if hist.empty:
            st.warning(f"No price history found for {selected_security}.")
            return

        st.subheader("Charts")

        chart_c1, chart_c2, chart_c3 = st.columns([1, 1, 1])

        with chart_c1:
            selected_period = st.selectbox(
                "Preset Window",
                ["5D", "30D", "3M", "6M", "1Y"],
                index=3,
            )

        default_start, default_end = compute_default_date_range(hist, selected_period)

        with chart_c2:
            start_date = st.date_input(
                "Start Date",
                value=default_start,
                min_value=hist.index.min().date(),
                max_value=hist.index.max().date(),
                key=f"start_{selected_security}_{selected_period}",
            )

        with chart_c3:
            end_date = st.date_input(
                "End Date",
                value=default_end,
                min_value=hist.index.min().date(),
                max_value=hist.index.max().date(),
                key=f"end_{selected_security}_{selected_period}",
            )

        if start_date > end_date:
            start_date, end_date = end_date, start_date

        st.caption(f"Displaying {selected_security} from {start_date} to {end_date}")

        render_price_chart(hist, selected_security, start_date, end_date)
        render_volume_chart(hist, selected_security, start_date, end_date)

        with st.expander(f"Show {selected_security} raw price history"):
            st.dataframe(hist.tail(20), use_container_width=True)