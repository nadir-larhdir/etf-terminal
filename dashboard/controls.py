

import pandas as pd
import streamlit as st


class BloombergControls:
    def render_select(self, label: str, options: list[str], *, index: int = 0, key: str) -> str:
        return st.selectbox(label, options, index=index, key=key)

    def render_date_range(
        self,
        *,
        start_label: str,
        end_label: str,
        default_start,
        default_end,
        min_date,
        max_date,
        start_key: str,
        end_key: str,
        columns_ratio: list[int] | None = None,
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        ratios = columns_ratio if columns_ratio is not None else [1, 1]
        c1, c2 = st.columns(ratios)

        with c1:
            start_date = st.date_input(
                start_label,
                value=default_start,
                min_value=min_date,
                max_value=max_date,
                key=start_key,
            )

        with c2:
            end_date = st.date_input(
                end_label,
                value=default_end,
                min_value=min_date,
                max_value=max_date,
                key=end_key,
            )

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts

        return start_ts, end_ts

    def render_window_and_dates(
        self,
        *,
        window_label: str,
        window_options: list[str],
        window_index: int,
        window_key: str,
        start_label: str,
        end_label: str,
        default_start,
        default_end,
        min_date,
        max_date,
        start_key: str,
        end_key: str,
    ) -> tuple[str, pd.Timestamp, pd.Timestamp]:
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            selected_window = st.selectbox(
                window_label,
                window_options,
                index=window_index,
                key=window_key,
            )

        with c2:
            start_date = st.date_input(
                start_label,
                value=default_start,
                min_value=min_date,
                max_value=max_date,
                key=start_key,
            )

        with c3:
            end_date = st.date_input(
                end_label,
                value=default_end,
                min_value=min_date,
                max_value=max_date,
                key=end_key,
            )

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts

        return selected_window, start_ts, end_ts