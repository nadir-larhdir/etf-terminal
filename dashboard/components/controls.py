from typing import Literal
from datetime import timedelta

import pandas as pd
import streamlit as st


class DashboardControls:
    """Provide shared Streamlit selectors and date controls for the dashboard."""

    WINDOW_DAY_MAP = {
        "5D": 5,
        "30D": 30,
        "3M": 63,
        "6M": 126,
        "1Y": 252,
    }

    def render_security_select(
        self,
        label: str,
        securities: pd.DataFrame,
        *,
        key: str,
        width: int | Literal["stretch"] = "stretch",
    ) -> str:
        options_df = securities.copy()

        if options_df.empty or "ticker" not in options_df.columns:
            return ""

        if "asset_class" not in options_df.columns:
            options_df["asset_class"] = "Other"
        if "name" not in options_df.columns:
            options_df["name"] = options_df["ticker"]

        options_df["ticker"] = options_df["ticker"].astype(str)
        options_df["asset_class"] = options_df["asset_class"].fillna("Other").astype(str)
        options_df["name"] = options_df["name"].fillna(options_df["ticker"]).astype(str)

        options_df = options_df.sort_values(["asset_class", "ticker"]).reset_index(drop=True)

        search_value = st.text_input(
            f"Search {label}",
            value="",
            key=f"{key}_search",
            placeholder="Type ticker...",
        ).strip().upper()

        if search_value:
            filtered_df = options_df.loc[
                options_df["ticker"].str.upper().str.contains(search_value, na=False)
            ].copy()
            if filtered_df.empty:
                filtered_df = options_df.loc[
                    options_df["name"].str.upper().str.contains(search_value, na=False)
                ].copy()
        else:
            filtered_df = options_df.copy()

        ticker_options = filtered_df["ticker"].tolist()
        if not ticker_options:
            st.caption("No matching securities.")
            return ""

        label_map = {
            row["ticker"]: str(row["ticker"])
            for _, row in filtered_df.iterrows()
        }

        selected = st.selectbox(
            label,
            ticker_options,
            key=key,
            width=width,
            format_func=lambda ticker: label_map.get(str(ticker), str(ticker)),
        )
        return str(selected) if selected is not None else ""

    def render_select(
        self,
        label: str,
        options: list[str],
        *,
        index: int = 0,
        key: str,
        width: int | Literal["stretch"] = "stretch",
    ) -> str:
        if not options:
            return ""
        selected = st.selectbox(label, options, index=index, key=key, width=width)
        return str(selected) if selected is not None else ""

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
        width: int | Literal["stretch"] = "stretch",
    ) -> tuple[str, pd.Timestamp, pd.Timestamp]:
        c1, c2, c3 = st.columns([0.9, 1, 1])

        with c1:
            selected_window = st.selectbox(
                window_label,
                window_options,
                index=window_index,
                key=window_key,
                width=width,
            )

        applied_window_key = f"{window_key}__applied"
        if st.session_state.get(applied_window_key) != selected_window:
            lookback_days = self.WINDOW_DAY_MAP.get(selected_window)
            if lookback_days is not None:
                computed_start = max_date - timedelta(days=lookback_days)
                st.session_state[start_key] = max(computed_start, min_date)
                st.session_state[end_key] = max_date
            elif str(selected_window).upper() == "ALL":
                st.session_state[start_key] = min_date
                st.session_state[end_key] = max_date
            else:
                st.session_state[start_key] = default_start
                st.session_state[end_key] = default_end
            st.session_state[applied_window_key] = selected_window
        else:
            st.session_state.setdefault(start_key, default_start)
            st.session_state.setdefault(end_key, default_end)

        with c2:
            start_date = st.date_input(
                start_label,
                min_value=min_date,
                max_value=max_date,
                key=start_key,
            )

        with c3:
            end_date = st.date_input(
                end_label,
                min_value=min_date,
                max_value=max_date,
                key=end_key,
            )

        start_ts = pd.Timestamp(start_date)
        end_ts = pd.Timestamp(end_date)
        if start_ts > end_ts:
            start_ts, end_ts = end_ts, start_ts

        return selected_window, start_ts, end_ts
