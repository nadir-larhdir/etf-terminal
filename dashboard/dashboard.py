from datetime import date
import streamlit as st
from config import PERIOD_OPTIONS
from dashboard.styles import APP_CSS
from dashboard.charts import ChartBuilder
from services.analytics_service import AnalyticsService


class Dashboard:
    def __init__(self, security_repo, price_repo, input_repo):
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.input_repo = input_repo
        self.analytics = AnalyticsService()
        self.chart_builder = ChartBuilder()

    def render_security_header(self, snapshot_row, selected_security: str):
        move = float(snapshot_row["pct_change"])
        price = float(snapshot_row["price"])
        flow = float(snapshot_row["flow_usd_mm"])
        premium_discount = float(snapshot_row["premium_discount_pct"])
        volume_ratio = float(snapshot_row["volume_vs_30d"])
        liquidity = str(snapshot_row["liquidity_regime"])
        move_class = "bb-pos" if move >= 0 else "bb-neg"
        pd_class = "bb-pos" if premium_discount >= 0 else "bb-neg"
        st.markdown(f"""
        <div class="bb-panel">
            <div class="bb-header-grid">
                <div class="bb-header-cell"><div class="bb-header-label">Security</div><div class="bb-header-value">{selected_security}</div></div>
                <div class="bb-header-cell"><div class="bb-header-label">Last Price</div><div class="bb-header-value">{price:,.2f}</div></div>
                <div class="bb-header-cell"><div class="bb-header-label">Daily Move</div><div class="bb-header-value {move_class}">{move:+.2f}%</div></div>
                <div class="bb-header-cell"><div class="bb-header-label">Flow</div><div class="bb-header-value">{flow:,.0f} mm</div></div>
                <div class="bb-header-cell"><div class="bb-header-label">Prem/Disc</div><div class="bb-header-value {pd_class}">{premium_discount:+.2f}%</div></div>
                <div class="bb-header-cell"><div class="bb-header-label">Vol vs 30D</div><div class="bb-header-value">{volume_ratio:.2f}x | {liquidity}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    def build_snapshot(self, tickers: list[str]):
        rows = []
        for ticker in tickers:
            hist = self.price_repo.get_price_history(ticker)
            latest_inputs = self.input_repo.get_latest_inputs(ticker)
            if hist.empty:
                continue
            latest = hist.iloc[-1]
            prev_close = hist.iloc[-2]["close"] if len(hist) > 1 else latest["close"]
            last_vol = float(latest["volume"])
            avg_30 = float(hist["volume"].tail(30).mean()) if len(hist) >= 1 else 0.0
            volume_vs = last_vol / avg_30 if avg_30 else 0.0
            premium_discount = float(latest_inputs.get("premium_discount_pct", 0.0) or 0.0)
            rows.append({
                "ticker": ticker,
                "price": float(latest["close"]),
                "pct_change": (float(latest["close"]) / float(prev_close) - 1.0) * 100 if prev_close else 0.0,
                "volume": last_vol,
                "30d_avg_volume": avg_30,
                "volume_vs_30d": volume_vs,
                "flow_usd_mm": float(latest_inputs.get("flow_usd_mm", 0.0) or 0.0),
                "premium_discount_pct": premium_discount,
                "liquidity_regime": self.analytics.classify_liquidity(volume_vs),
                "rv_signal": self.analytics.classify_rv(premium_discount),
                "desk_note": latest_inputs.get("desk_note", "") or "",
            })
        return rows

    def run(self):
        st.set_page_config(page_title="ETF MONITOR", layout="wide")
        st.markdown(APP_CSS, unsafe_allow_html=True)
        st.title("ETF MONITOR")
        st.caption("BLOOMBERG-STYLE MOCK DASHBOARD FOR ETF FLOW / LIQUIDITY / RV MONITORING")

        securities = self.security_repo.get_all()
        tickers = securities["ticker"].tolist()
        st.subheader("Security Monitor")

        selector_c1, selector_c2 = st.columns([1.2, 2])
        with selector_c1:
            selected_security = st.selectbox("Security", options=tickers, index=0)
        with selector_c2:
            st.markdown("<div style='height: 1.9rem;'></div>", unsafe_allow_html=True)
            st.caption("SELECT ONE SECURITY TO DRIVE HEADER, CHARTS, NOTES, AND COMMENTARY")

        latest_inputs = self.input_repo.get_latest_inputs(selected_security)
        input_c1, input_c2 = st.columns(2)
        with input_c1:
            selected_flow = st.number_input(f"{selected_security} flow", value=float(latest_inputs["flow_usd_mm"]), step=10.0)
        with input_c2:
            selected_pd = st.number_input(f"{selected_security} premium/discount", value=float(latest_inputs["premium_discount_pct"]), step=0.1)

        snapshot_rows = self.build_snapshot(tickers)
        selected_snapshot = next(row for row in snapshot_rows if row["ticker"] == selected_security)
        selected_snapshot["flow_usd_mm"] = selected_flow
        selected_snapshot["premium_discount_pct"] = selected_pd
        selected_snapshot["rv_signal"] = self.analytics.classify_rv(selected_pd)
        self.render_security_header(selected_snapshot, selected_security)

        st.subheader("Charts")
        hist = self.price_repo.get_price_history(selected_security)
        if not hist.empty:
            chart_c1, chart_c2, chart_c3 = st.columns([1, 1, 1])
            with chart_c1:
                selected_period = st.selectbox("Preset Window", options=list(PERIOD_OPTIONS.keys()), index=3)
            rows = PERIOD_OPTIONS[selected_period]
            filtered = self.analytics.filter_history_by_rows(hist, rows)
            default_start = filtered.index.min().date()
            default_end = filtered.index.max().date()
            with chart_c2:
                start_date = st.date_input("Start Date", value=default_start, min_value=hist.index.min().date(), max_value=hist.index.max().date())
            with chart_c3:
                end_date = st.date_input("End Date", value=default_end, min_value=hist.index.min().date(), max_value=hist.index.max().date())
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            cc1, cc2 = st.columns(2)
            with cc1:
                st.plotly_chart(self.chart_builder.build_price_chart(hist, selected_security, start_date, end_date), use_container_width=True)
            with cc2:
                st.plotly_chart(self.chart_builder.build_volume_chart(hist, selected_security, start_date, end_date), use_container_width=True)

        st.subheader("Desk Notes")
        desk_note = st.text_area(f"{selected_security} note", value=latest_inputs["desk_note"], height=120)
        if st.button("Save inputs"):
            self.input_repo.upsert_inputs(selected_security, None, selected_flow, selected_pd, desk_note)
            st.success("Inputs saved.")

        st.subheader("Auto Commentary")
        st.write(
            f"- {selected_security}: move {selected_snapshot['pct_change']:+.2f}%, "
            f"flow {selected_flow:,.0f}mm, premium/discount {selected_pd:+.2f}%, "
            f"volume vs 30D avg {selected_snapshot['volume_vs_30d']:.2f}x, "
            f"liquidity {selected_snapshot['liquidity_regime']}, RV {selected_snapshot['rv_signal']}."
        )
