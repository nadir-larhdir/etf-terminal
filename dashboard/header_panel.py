

import pandas as pd
import streamlit as st


class HeaderPanel:
    def render_description(
        self,
        securities: pd.DataFrame,
        selected_security: str,
        metadata: dict | None,
    ) -> None:
        selected_row = securities.loc[securities["ticker"] == selected_security].iloc[0]
        security_name = selected_row["name"]
        asset_class = selected_row["asset_class"]

        st.markdown(
            f"""
            <div style="
                border: 1px solid #2A2A2A;
                background-color: #050505;
                padding: 0.60rem 0.75rem;
                margin-top: 1.55rem;
                border-radius: 2px;
            ">
                <div style="color:#FF9F1A; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.35px; margin-bottom:0.18rem;">
                    ETF Description
                </div>
                <div style="color:#F3F0E8; font-size:0.96rem; font-weight:700; margin-bottom:0.28rem;">
                    {selected_security} — {metadata.get('long_name', security_name) if metadata else security_name}
                </div>
                <div style="color:#B8B1A3; font-size:0.92rem; line-height:1.45; margin-bottom:0.35rem;">
                    {metadata.get('description', f'This ETF is currently classified in the dashboard as {asset_class}.') if metadata else f'This ETF is currently classified in the dashboard as {asset_class}.'}
                </div>
                <div style="color:#B8B1A3; font-size:0.88rem; line-height:1.45;">
                    <span style="color:#F3F0E8; font-weight:700;">Category:</span> {metadata.get('category', asset_class) if metadata else asset_class}
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    <span style="color:#F3F0E8; font-weight:700;">Benchmark:</span> {metadata.get('benchmark_index', 'N/A') if metadata else 'N/A'}
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    <span style="color:#F3F0E8; font-weight:700;">Duration:</span> {metadata.get('duration_bucket', 'N/A') if metadata else 'N/A'}
                    &nbsp;&nbsp;|&nbsp;&nbsp;
                    <span style="color:#F3F0E8; font-weight:700;">Issuer:</span> {metadata.get('issuer', 'N/A') if metadata else 'N/A'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def render_header_strip(self, hist: pd.DataFrame, selected_security: str) -> None:
        px_last = float(hist["close"].iloc[-1])
        prev_close = float(hist["close"].iloc[-2]) if len(hist) > 1 else px_last
        chg = px_last - prev_close
        chg_pct = (chg / prev_close * 100) if prev_close != 0 else 0.0

        volume = int(hist["volume"].iloc[-1])
        vol_30d = float(hist["volume"].tail(30).mean()) if len(hist) >= 1 else float(volume)
        vol_ratio = (volume / vol_30d) if vol_30d else 0.0

        chg_color = "#00C176" if chg >= 0 else "#FF5A36"

        st.markdown(
            f"""
            <div style="
                border: 1px solid #2A2A2A;
                background-color: #050505;
                padding: 0.45rem 0.55rem;
                margin: 0.2rem 0 0.65rem 0;
                border-radius: 2px;
            ">
                <div style="
                    display:grid;
                    grid-template-columns: 1.2fr 1fr 1fr 1fr 1fr;
                    gap: 0.4rem;
                    align-items:stretch;
                ">
                    <div style="border:1px solid #2A2A2A; background:#0A0A0A; padding:0.35rem 0.45rem;">
                        <div style="color:#B8B1A3; font-size:0.68rem; text-transform:uppercase;">Security</div>
                        <div style="color:#F3F0E8; font-size:0.95rem; font-weight:700;">{selected_security}</div>
                    </div>
                    <div style="border:1px solid #2A2A2A; background:#0A0A0A; padding:0.35rem 0.45rem;">
                        <div style="color:#B8B1A3; font-size:0.68rem; text-transform:uppercase;">PX_LAST</div>
                        <div style="color:#F3F0E8; font-size:0.95rem; font-weight:700;">{px_last:,.2f}</div>
                    </div>
                    <div style="border:1px solid #2A2A2A; background:#0A0A0A; padding:0.35rem 0.45rem;">
                        <div style="color:#B8B1A3; font-size:0.68rem; text-transform:uppercase;">CHG</div>
                        <div style="color:{chg_color}; font-size:0.95rem; font-weight:700;">{chg:+,.2f}</div>
                    </div>
                    <div style="border:1px solid #2A2A2A; background:#0A0A0A; padding:0.35rem 0.45rem;">
                        <div style="color:#B8B1A3; font-size:0.68rem; text-transform:uppercase;">CHG %</div>
                        <div style="color:{chg_color}; font-size:0.95rem; font-weight:700;">{chg_pct:+.2f}%</div>
                    </div>
                    <div style="border:1px solid #2A2A2A; background:#0A0A0A; padding:0.35rem 0.45rem;">
                        <div style="color:#B8B1A3; font-size:0.68rem; text-transform:uppercase;">VOLUME / 30D</div>
                        <div style="color:#F3F0E8; font-size:0.95rem; font-weight:700;">{volume:,.0f} / {vol_ratio:.2f}x</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )