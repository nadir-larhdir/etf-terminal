import uuid
import pandas as pd
import streamlit as st


class DashboardTable:
    """Style and render dataframe outputs in the dashboard table theme."""

    def _style_dataframe(self, df: pd.DataFrame):
        styled = df.style

        def style_value(value, column_name: str) -> str:
            is_text_col = column_name.upper() in {"DATE", "PAIR", "REGIME", "CROSS"}
            text_align = "left" if is_text_col else "right"
            base_style = f"color:#1F271C; text-align:{text_align};"

            try:
                numeric_value = float(str(value).replace(",", ""))

                if "Z" in column_name.upper():
                    intensity = min(abs(numeric_value) / 3.0, 1.0)
                    alpha = 0.18 + 0.30 * intensity
                    if numeric_value > 0:
                        bar_color = f"rgba(0, 193, 118, {alpha:.2f})"
                        text_color = "#4E7B52"
                    elif numeric_value < 0:
                        bar_color = f"rgba(165, 92, 69, {alpha:.2f})"
                        text_color = "#A55C45"
                    else:
                        bar_color = "rgba(255,255,255,0.00)"
                        text_color = "#1F271C"

                    weight = "700" if abs(numeric_value) >= 2 else "400"
                    edge = "#6F7B46" if abs(numeric_value) >= 2 else "transparent"
                    return (
                        f"color:{text_color};"
                        f"font-weight:{weight};"
                        f"text-align:{text_align};"
                        f"background:linear-gradient(90deg, {bar_color} 0%, {bar_color} 100%);"
                        f"box-shadow: inset 0 0 0 1px {edge};"
                    )

                if "CORR" in column_name.upper() or "STABILITY" in column_name.upper():
                    if numeric_value >= 0.8:
                        return f"color:#4E7B52; font-weight:700; text-align:{text_align};"
                    if numeric_value <= 0.3:
                        return f"color:#6F7B46; text-align:{text_align};"
                    return base_style

                return base_style
            except Exception:
                regime_text = str(value).upper()
                if regime_text in {"RICH / EXTREME", "RICH"}:
                    return f"color:#A55C45; font-weight:700; text-align:{text_align};"
                if regime_text in {"CHEAP / EXTREME", "CHEAP"}:
                    return f"color:#4E7B52; font-weight:700; text-align:{text_align};"
                if regime_text == "NEUTRAL":
                    return f"color:#1F271C; text-align:{text_align};"
                return base_style

        def style_frame(frame: pd.DataFrame) -> pd.DataFrame:
            styled_frame = pd.DataFrame("", index=frame.index, columns=frame.columns)
            for col in frame.columns:
                styled_frame[col] = frame[col].map(lambda x, col_name=col: style_value(x, col_name))
            return styled_frame

        styled = styled.apply(style_frame, axis=None)

        styled = styled.set_table_attributes('class="core-table"')
        styled = styled.set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#F1EDE3"),
                        ("color", "#1F271C"),
                        ("font-weight", "700"),
                        ("text-transform", "uppercase"),
                        ("letter-spacing", "0.30px"),
                        ("font-size", "0.68rem"),
                        ("padding", "0.22rem 0.40rem"),
                        ("border-bottom", "1px solid #D8D4C7"),
                        ("border-right", "1px solid #D8D4C7"),
                        ("text-align", "left"),
                        ("white-space", "nowrap"),
                    ],
                },
                {
                    "selector": "td",
                    "props": [
                        ("background-color", "#FBF8F1"),
                        ("padding", "0.18rem 0.40rem"),
                        ("font-size", "0.74rem"),
                        ("border-bottom", "1px solid #E0DCCF"),
                        ("border-right", "1px solid #E0DCCF"),
                        ("white-space", "nowrap"),
                    ],
                },
            ]
        )
        return styled

    def _prepare_display_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        display_df = df.copy()

        for col in display_df.columns:
            if col in {"PAIR", "DATE", "REGIME", "CROSS"}:
                continue

            numeric_series = pd.to_numeric(display_df[col], errors="coerce")
            if numeric_series.notna().any():
                if col == "STABILITY":
                    display_df[col] = numeric_series.map(
                        lambda x: f"{x:.0f}" if pd.notna(x) else ""
                    )
                elif (numeric_series.dropna() % 1 == 0).all():
                    display_df[col] = numeric_series.map(
                        lambda x: f"{int(x):,}" if pd.notna(x) else ""
                    )
                else:
                    display_df[col] = numeric_series.map(
                        lambda x: f"{x:.2f}" if pd.notna(x) else ""
                    )

        return display_df

    def render(
        self, df: pd.DataFrame, *, hide_index: bool = True, height: int | None = None
    ) -> None:
        table_id = f"core-table-{uuid.uuid4().hex[:8]}"
        display_df = self._prepare_display_dataframe(df)

        if hide_index:
            display_df = display_df.reset_index(drop=True)
        styled = self._style_dataframe(display_df)
        html_table = styled.hide(axis="index").to_html(index=False, escape=False)

        effective_height = height if height is not None else 300
        container_style = f"max-height:{effective_height}px; overflow-y:auto;"

        html = f"""
<style>
.{table_id}-wrap {{
    border: 1px solid #D8D4C7;
    border-radius: 0;
    background-color: #FBF8F1;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.55);
    width: 100%;
    overflow-x: auto;
    {container_style}
}}

.{table_id}-wrap table {{
    width: 100%;
    border-collapse: collapse;
    background-color: #FBF8F1;
    color: #1F271C;
    font-size: 0.76rem;
    table-layout: auto;
}}

.{table_id}-wrap thead th {{
    position: sticky;
    top: 0;
    z-index: 1;
}}

.{table_id}-wrap tbody tr:hover td {{
    background-color: #F1EDE3 !important;
}}

.{table_id}-wrap tbody tr:nth-child(even) td {{
    background-color: #F7F3EA !important;
}}

.{table_id}-wrap thead th:last-child,
.{table_id}-wrap tbody td:last-child {{
    border-right: none !important;
}}

.{table_id}-wrap tbody tr:last-child td {{
    border-bottom: none !important;
}}
</style>
<div class="{table_id}-wrap">
{html_table}
</div>
"""
        st.html(html)

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

    def format_screener(self, df: pd.DataFrame) -> pd.DataFrame:
        formatted = df.copy()

        for col in formatted.columns:
            if col == "PAIR":
                continue
            if col == "STABILITY":
                formatted[col] = formatted[col].map(
                    lambda x: f"{float(x):.0f}" if pd.notna(x) else ""
                )
            else:
                formatted[col] = formatted[col].map(
                    lambda x: f"{float(x):.2f}" if pd.notna(x) else ""
                )

        return formatted
