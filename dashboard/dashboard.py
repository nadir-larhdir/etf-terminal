import streamlit as st
import plotly.graph_objects as go
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

        tab_graphs, tab_analytics, tab_rv = st.tabs(["Graphs", "Analytics", "RV Analysis"])

        with tab_graphs:
            st.subheader("Charts")

            chart_c1, chart_c2, chart_c3 = st.columns([1, 1, 1])

            with chart_c1:
                selected_period = st.selectbox(
                    "Preset Window",
                    ["5D", "30D", "3M", "6M", "1Y"],
                    index=3,
                    key=f"graphs_period_{selected_security}",
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

        with tab_analytics:
            st.subheader("Analytics")

            px_last = float(hist["close"].iloc[-1])
            prev_close = float(hist["close"].iloc[-2]) if len(hist) > 1 else px_last
            chg_pct = ((px_last - prev_close) / prev_close * 100) if prev_close != 0 else 0.0

            volume = hist["volume"]
            vol_mean_30d = float(volume.tail(30).mean()) if len(volume) >= 1 else float(volume.iloc[-1])
            current_vol = float(volume.iloc[-1])
            vol_std_30d = float(volume.tail(30).std(ddof=0)) if len(volume.tail(30)) > 1 else 0.0
            vol_z = (current_vol - vol_mean_30d) / vol_std_30d if vol_std_30d != 0 else 0.0

            high = float(hist["high"].iloc[-1])
            low = float(hist["low"].iloc[-1])
            range_position = ((px_last - low) / (high - low)) if high != low else 0.5

            if vol_z > 2:
                liquidity_regime = "HIGH ACTIVITY"
            elif vol_z < -1:
                liquidity_regime = "QUIET"
            else:
                liquidity_regime = "NORMAL"

            a1, a2, a3, a4 = st.columns(4)
            with a1:
                st.metric("PX_LAST", f"{px_last:,.2f}", f"{chg_pct:+.2f}%")
            with a2:
                st.metric("VOL / 30D", f"{current_vol:,.0f}", f"{(current_vol / vol_mean_30d):.2f}x" if vol_mean_30d else "0.00x")
            with a3:
                st.metric("VOL Z-SCORE", f"{vol_z:,.2f}")
            with a4:
                st.metric("RANGE POS", f"{range_position:.2%}")

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


        with tab_rv:
            st.subheader("RV Analysis")

            rv_candidates = [ticker for ticker in tickers if ticker != selected_security]
            compare_security = st.selectbox(
                "Compare With",
                rv_candidates,
                key=f"rv_compare_{selected_security}",
            )

            compare_hist = self.price_repo.get_price_history(compare_security)

            if compare_hist.empty:
                st.warning(f"No price history found for {compare_security}.")
            else:
                merged = hist[["close"]].join(
                    compare_hist[["close"]],
                    how="inner",
                    lsuffix="_base",
                    rsuffix="_comp",
                ).dropna()

                if merged.empty:
                    st.warning("No overlapping history available for RV analysis.")
                else:
                    merged["ratio"] = merged["close_base"] / merged["close_comp"]
                    ratio_mean = float(merged["ratio"].mean())
                    ratio_std = float(merged["ratio"].std(ddof=0)) if len(merged) > 1 else 0.0

                    if ratio_std != 0:
                        merged["zscore"] = (merged["ratio"] - ratio_mean) / ratio_std
                    else:
                        merged["zscore"] = 0.0

                    current_ratio = float(merged["ratio"].iloc[-1])
                    current_z = float(merged["zscore"].iloc[-1])

                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.metric("PAIR", f"{selected_security} / {compare_security}")
                    with r2:
                        st.metric("RATIO", f"{current_ratio:,.4f}")
                    with r3:
                        st.metric("Z-SCORE", f"{current_z:,.2f}")

                    z_min = min(float(merged["zscore"].min()), -2.0)
                    z_max = max(float(merged["zscore"].max()), 2.0)
                    z_padding = max((z_max - z_min) * 0.12, 0.25)

                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=merged.index,
                            y=merged["zscore"],
                            mode="lines",
                            name="Z-Score",
                            line=dict(color="#7EC8FF", width=2.2),
                            hovertemplate="%{x|%b %d, %Y}<br>Z-SCORE: %{y:,.2f}<extra></extra>",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=merged.index,
                            y=[0.0] * len(merged),
                            mode="lines",
                            name="Mean",
                            line=dict(color="#FF9F1A", width=1.4),
                            hovertemplate="MEAN: %{y:,.2f}<extra></extra>",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=merged.index,
                            y=[1.0] * len(merged),
                            mode="lines",
                            name="+1σ",
                            line=dict(color="#FFD166", width=1, dash="dot"),
                            hovertemplate="+1σ: %{y:,.2f}<extra></extra>",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=merged.index,
                            y=[-1.0] * len(merged),
                            mode="lines",
                            name="-1σ",
                            line=dict(color="#FFD166", width=1, dash="dot"),
                            hovertemplate="-1σ: %{y:,.2f}<extra></extra>",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=merged.index,
                            y=[2.0] * len(merged),
                            mode="lines",
                            name="+2σ",
                            line=dict(color="#FF5A36", width=1, dash="dash"),
                            hovertemplate="+2σ: %{y:,.2f}<extra></extra>",
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=merged.index,
                            y=[-2.0] * len(merged),
                            mode="lines",
                            name="-2σ",
                            line=dict(color="#FF5A36", width=1, dash="dash"),
                            hovertemplate="-2σ: %{y:,.2f}<extra></extra>",
                        )
                    )

                    fig.update_layout(
                        title=dict(text=f"{selected_security} / {compare_security} RV Z-Score", x=0.02, xanchor="left"),
                        template="plotly_dark",
                        paper_bgcolor="#000000",
                        plot_bgcolor="#000000",
                        font=dict(
                            color="#F3F0E8",
                            family='"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                            size=12,
                        ),
                        margin=dict(l=20, r=20, t=50, b=30),
                        height=520,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="center",
                            x=0.5,
                            font=dict(size=10),
                            bgcolor="rgba(0,0,0,0)",
                        ),
                        xaxis=dict(
                            title="Date",
                            showgrid=True,
                            gridcolor="#2A2A2A",
                            zeroline=False,
                            range=[merged.index.min(), merged.index.max()],
                            rangeslider=dict(visible=False),
                            fixedrange=True,
                        ),
                        yaxis=dict(
                            title="Z-Score",
                            showgrid=True,
                            gridcolor="#2A2A2A",
                            zeroline=False,
                            range=[z_min - z_padding, z_max + z_padding],
                            tickformat=".2f",
                            fixedrange=True,
                        ),
                    )

                    st.plotly_chart(fig, use_container_width=True)