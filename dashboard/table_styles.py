import pandas as pd
import streamlit as st


class BloombergTable:
    def render(self, df: pd.DataFrame, *, hide_index: bool = True, height: int | None = None) -> None:
        st.markdown(
            """
            <style>
            div[data-testid="stDataFrame"] {
                border: 1px solid #2A2A2A;
                border-radius: 2px;
                background-color: #050505;
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.01);
            }
            div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {
                background-color: #050505;
            }
            div[data-testid="stDataFrame"] table {
                color: #F3F0E8;
                font-size: 0.82rem;
            }
            div[data-testid="stDataFrame"] thead tr th {
                background-color: #11151C !important;
                color: #00ADB5 !important;
                font-weight: 700 !important;
                border-bottom: 1px solid #2A2A2A !important;
                letter-spacing: 0.3px;
            }
            div[data-testid="stDataFrame"] tbody tr td {
                background-color: #050505 !important;
                color: #F3F0E8 !important;
                border-bottom: 1px solid #161A22 !important;
            }
            div[data-testid="stDataFrame"] tbody tr:hover td {
                background-color: #0E1117 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        if height is not None:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=hide_index,
                height=height,
            )
        else:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=hide_index,
            )

    def format_history(self, df: pd.DataFrame) -> pd.DataFrame:
        formatted = df.copy()

        for col in ["open", "high", "low", "close", "adj_close"]:
            if col in formatted.columns:
                formatted[col] = formatted[col].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "")

        if "volume" in formatted.columns:
            formatted["volume"] = formatted["volume"].map(
                lambda x: f"{int(x):,}" if pd.notna(x) else ""
            )

        if "date" in formatted.columns:
            formatted["date"] = pd.to_datetime(formatted["date"]).dt.strftime("%Y-%m-%d")

        return formatted

    def format_signal_history(self, df: pd.DataFrame) -> pd.DataFrame:
        formatted = df.copy()
        if "DATE" in formatted.columns:
            formatted["DATE"] = pd.to_datetime(formatted["DATE"]).dt.strftime("%Y-%m-%d")
        return formatted