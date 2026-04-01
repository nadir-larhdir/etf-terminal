import pandas as pd
import streamlit as st

from dashboard.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)
from dashboard.table_styles import BloombergTable
from dashboard.controls import BloombergControls


class GraphsTab:
    def __init__(self) -> None:
        self.table = BloombergTable()
        self.controls = BloombergControls()

    def render(self, hist: pd.DataFrame, selected_security: str) -> None:
        st.subheader("Charts")

        selected_period = self.controls.render_select(
            "Preset Window",
            ["5D", "30D", "3M", "6M", "1Y"],
            index=3,
            key=f"graphs_period_{selected_security}",
        )

        default_start, default_end = compute_default_date_range(hist, selected_period)

        start_date, end_date = self.controls.render_date_range(
            start_label="Start Date",
            end_label="End Date",
            default_start=default_start,
            default_end=default_end,
            min_date=hist.index.min().date(),
            max_date=hist.index.max().date(),
            start_key=f"start_{selected_security}_{selected_period}",
            end_key=f"end_{selected_security}_{selected_period}",
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