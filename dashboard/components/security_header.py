import pandas as pd
import streamlit as st

from dashboard.components.info_panel import InfoPanel


class SecurityHeader:
    """Render the descriptive and top-strip header blocks for the selected ETF."""

    def __init__(self) -> None:
        self.info_panel = InfoPanel()

    def _format_aum(self, value) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "N/A"

        if numeric >= 1_000_000_000:
            return f"{numeric / 1_000_000_000:.1f}B"
        if numeric >= 1_000_000:
            return f"{numeric / 1_000_000:.1f}M"
        if numeric >= 1_000:
            return f"{numeric / 1_000:.1f}K"
        return f"{numeric:,.0f}"

    def _format_expense_ratio(self, value) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "N/A"
        return f"{numeric:.2f}%"

    def _header_cell_html(
        self,
        label: str,
        value: str,
        *,
        color: str = "#1F271C",
        emphasis: str = "standard",
    ) -> str:
        primary_class = " bb-summary-cell--primary" if emphasis == "primary" else ""
        value_class = " bb-summary-value--primary" if emphasis == "primary" else ""
        return (
            f'<div class="bb-summary-cell{primary_class}">'
            f'<div class="bb-summary-label">{label}</div>'
            f'<div class="bb-summary-value{value_class}" style="color:{color};">{value}</div>'
            "</div>"
        )

    def render_description(
        self,
        securities: pd.DataFrame,
        selected_security: str,
        metadata: dict | None,
    ) -> None:
        selected_matches = securities.loc[
            securities["ticker"].astype(str) == str(selected_security)
        ]
        if selected_matches.empty:
            st.warning(f"Security metadata not found for {selected_security}.")
            return
        selected_row = selected_matches.iloc[0]
        security_name = selected_row["name"]
        asset_class = selected_row["asset_class"]

        headline = f"{selected_security} — {metadata.get('long_name', security_name) if metadata else security_name}"
        body = (
            metadata.get(
                "description",
                f"This ETF is currently classified in the dashboard as {asset_class}.",
            )
            if metadata
            else f"This ETF is currently classified in the dashboard as {asset_class}."
        )

        footer = (
            f"<span style='color:#1F271C; font-weight:700;'>Category:</span> {metadata.get('category', asset_class) if metadata else asset_class}"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<span style='color:#1F271C; font-weight:700;'>Benchmark:</span> {metadata.get('benchmark_index', 'N/A') if metadata else 'N/A'}"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<span style='color:#1F271C; font-weight:700;'>Duration:</span> {metadata.get('duration_bucket', 'N/A') if metadata else 'N/A'}"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<span style='color:#1F271C; font-weight:700;'>Issuer:</span> {metadata.get('issuer', 'N/A') if metadata else 'N/A'}"
        )

        self.info_panel.render(
            title="ETF Description",
            headline=headline,
            body=body,
            footer=footer,
            margin_top="1.55rem",
            margin_bottom="0.00rem",
        )

    def render_header_strip(
        self, hist: pd.DataFrame, selected_security: str, metadata: dict | None = None
    ) -> None:
        metadata = metadata or {}
        px_last = float(hist["close"].iloc[-1])
        prev_close = float(hist["close"].iloc[-2]) if len(hist) > 1 else px_last
        chg = px_last - prev_close
        chg_pct = (chg / prev_close * 100) if prev_close != 0 else 0.0

        volume = int(hist["volume"].iloc[-1])
        vol_30d = float(hist["volume"].tail(30).mean()) if len(hist) >= 1 else float(volume)
        vol_ratio = (volume / vol_30d) if vol_30d else 0.0

        chg_color = "#4E7B52" if chg >= 0 else "#A55C45"
        header_cells = [
            self._header_cell_html("Security", selected_security, emphasis="primary"),
            self._header_cell_html("PX_LAST", f"{px_last:,.2f}", emphasis="primary"),
            self._header_cell_html("CHG", f"{chg:+,.2f}", color=chg_color, emphasis="primary"),
            self._header_cell_html(
                "CHG %", f"{chg_pct:+.2f}%", color=chg_color, emphasis="primary"
            ),
            self._header_cell_html("VOLUME / 30D", f"{volume:,.0f} / {vol_ratio:.2f}x"),
            self._header_cell_html("EXCHANGE", str(metadata.get("exchange", "N/A"))),
            self._header_cell_html("AUM", self._format_aum(metadata.get("total_assets"))),
            self._header_cell_html(
                "EXP RATIO", self._format_expense_ratio(metadata.get("expense_ratio"))
            ),
        ]

        st.markdown(
            f"""
            <div class="bb-summary-strip">
                <div class="bb-summary-grid">
                    {''.join(header_cells)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
