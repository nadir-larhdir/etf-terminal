import pandas as pd
import streamlit as st

from dashboard.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)


class GraphsTab:
    def render(self, hist: pd.DataFrame, selected_security: str) -> None:
        st.subheader("Charts")

        chart_c1, chart_c2, chart_c3 = st.columns([1, 1, 1])

        with chart_c1:
            selected_period = st.selectbox(
                "Preset Window",
                ["5D", "30D", "3M", "6M", "1Y"],
                index=3,
                key=f"graphs_period_{selected_security}",
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
            display_hist = hist.tail(20).copy().reset_index()
            display_hist = display_hist.rename(columns={"index": "date"})

            if "date" in display_hist.columns:
                display_hist["date"] = display_hist["date"].dt.strftime("%Y-%m-%d")

            for col in ["open", "high", "low", "close", "adj_close"]:
                if col in display_hist.columns:
                    display_hist[col] = display_hist[col].map(lambda x: f"{x:,.2f}")

            if "volume" in display_hist.columns:
                display_hist["volume"] = display_hist["volume"].map(
                    lambda x: f"{int(x):,}" if pd.notna(x) else ""
                )

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

            st.dataframe(display_hist, use_container_width=True, hide_index=True)