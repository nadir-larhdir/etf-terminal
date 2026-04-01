import streamlit as st
from dashboard.styles import apply_bloomberg_theme

from dashboard.charts import (
    compute_default_date_range,
    render_price_chart,
    render_volume_chart,
)


class Dashboard:
    def __init__(self, security_repo, price_repo, input_repo, metadata_repo):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.input_repo = input_repo
        self.metadata_repo = metadata_repo

    def _render_header_strip(self, hist, selected_security):
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

    def run(self):
        apply_bloomberg_theme()
        st.title("ETF MONITOR")
        st.caption("Database-backed ETF dashboard")

        securities = self.security_repo.get_all()
        tickers = securities["ticker"].tolist()

        if not tickers:
            st.warning("No active securities found in the database.")
            return

        selector_col, desc_col = st.columns([1, 2.4])

        with selector_col:
            selected_security = st.selectbox("Security", tickers)

        selected_row = securities.loc[securities["ticker"] == selected_security].iloc[0]
        security_name = selected_row["name"]
        asset_class = selected_row["asset_class"]
        metadata = self.metadata_repo.get_metadata(selected_security)

        with desc_col:
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

        hist = self.price_repo.get_price_history(selected_security)

        if hist.empty:
            st.warning(f"No price history found for {selected_security}.")
            return
        
        self._render_header_strip(hist, selected_security)

        st.subheader("Charts")

        chart_c1, chart_c2, chart_c3 = st.columns([1, 1, 1])

        with chart_c1:
            selected_period = st.selectbox(
                "Preset Window",
                ["5D", "30D", "3M", "6M", "1Y"],
                index=3,
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
                display_hist["volume"] = display_hist["volume"].map(lambda x: f"{int(x):,}")

            display_hist = display_hist.rename(columns={
                "date": "DATE",
                "open": "OPEN",
                "high": "HIGH",
                "low": "LOW",
                "close": "CLOSE",
                "adj_close": "ADJ CLOSE",
                "volume": "VOLUME",
            })

            st.dataframe(display_hist, use_container_width=True, hide_index=True)