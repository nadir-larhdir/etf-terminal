

import pandas as pd
import streamlit as st


class AnalyticsTab:
    def render(self, hist: pd.DataFrame) -> None:
        st.subheader("Analytics")

        # --- Price metrics ---
        px_last = float(hist["close"].iloc[-1])
        prev_close = float(hist["close"].iloc[-2]) if len(hist) > 1 else px_last
        chg_pct = ((px_last - prev_close) / prev_close * 100) if prev_close != 0 else 0.0

        # --- Volume metrics ---
        volume = hist["volume"]
        vol_mean_30d = float(volume.tail(30).mean()) if len(volume) >= 1 else float(volume.iloc[-1])
        current_vol = float(volume.iloc[-1])
        vol_std_30d = float(volume.tail(30).std(ddof=0)) if len(volume.tail(30)) > 1 else 0.0
        vol_z = (current_vol - vol_mean_30d) / vol_std_30d if vol_std_30d != 0 else 0.0

        # --- Range position ---
        high = float(hist["high"].iloc[-1])
        low = float(hist["low"].iloc[-1])
        range_position = ((px_last - low) / (high - low)) if high != low else 0.5

        # --- Liquidity regime ---
        if vol_z > 2:
            liquidity_regime = "HIGH ACTIVITY"
        elif vol_z < -1:
            liquidity_regime = "QUIET"
        else:
            liquidity_regime = "NORMAL"

        # --- Top metrics ---
        a1, a2, a3, a4 = st.columns(4)
        with a1:
            st.metric("PX_LAST", f"{px_last:,.2f}", f"{chg_pct:+.2f}%")
        with a2:
            st.metric(
                "VOL / 30D",
                f"{current_vol:,.0f}",
                f"{(current_vol / vol_mean_30d):.2f}x" if vol_mean_30d else "0.00x",
            )
        with a3:
            st.metric("VOL Z-SCORE", f"{vol_z:,.2f}")
        with a4:
            st.metric("RANGE POS", f"{range_position:.2%}")

        # --- Liquidity panel ---
        st.markdown(
            f"""
            <div style="
                border: 1px solid #2A2A2A;
                background-color: #050505;
                padding: 0.60rem 0.75rem;
                border-radius: 2px;
                margin-top: 0.35rem;
            ">
                <div style="color:#FF9F1A; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.35px; margin-bottom:0.18rem;">
                    Liquidity Regime
                </div>
                <div style="color:#F3F0E8; font-size:0.96rem; font-weight:700; margin-bottom:0.18rem;">
                    {liquidity_regime}
                </div>
                <div style="color:#B8B1A3; font-size:0.88rem; line-height:1.45;">
                    Based on current volume versus the trailing 30-day average and its standardized z-score.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )