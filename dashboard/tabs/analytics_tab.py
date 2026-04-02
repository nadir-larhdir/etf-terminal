import streamlit as st

from dashboard.components.info_panel import InfoPanel
from models.security import Security


class AnalyticsTab:
    """Display single-security liquidity and price diagnostics."""

    def __init__(self) -> None:
        self.info_panel = InfoPanel()

    def render(self, security: Security) -> None:
        st.subheader("Analytics")
        hist = security.history

        # --- Price metrics ---
        px_last = security.last_price() or 0.0
        close_series = security.close_series()
        prev_close = float(close_series.iloc[-2]) if len(close_series) > 1 else px_last
        chg_pct = ((px_last - prev_close) / prev_close * 100) if prev_close != 0 else 0.0

        # --- Volume metrics ---
        volume = security.volume_series()
        current_vol = security.last_volume() or 0.0
        vol_mean_30d = float(volume.tail(30).mean()) if not volume.empty else 0.0
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
        self.info_panel.render(
            title="Liquidity Regime",
            headline=liquidity_regime,
            body="Based on current volume versus the trailing 30-day average and its standardized z-score.",
            accent_color="#00ADB5",
            margin_top="0.35rem",
            margin_bottom="0.00rem",
        )
