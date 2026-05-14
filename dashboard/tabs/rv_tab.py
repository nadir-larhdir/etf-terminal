"""RV Analysis tab: relative-value cards, chart, framework panels, and pair screener."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from dashboard.cache import app_cache_key, cached_multi_price_history, cached_price_history
from dashboard.components.charts import (
    render_beta_adjusted_z_chart,
    render_return_spread_chart,
    render_zscore_chart,
)
from dashboard.components.controls import DashboardControls
from dashboard.perf import timed_block
from dashboard.styles.table_styles import DashboardTable
from fixed_income.etfs import ETF
from fixed_income.rv.pair_analytics import (
    beta_metrics,
    filtered_prices,
    rolling_correlation,
)
from fixed_income.rv.spread_definition import SpreadDefinition
from fixed_income.rv.spread_diagnostics import (
    diagnose_spread,
    forward_spread_reversion_stats,
    regime_from_zscore,
    spread_stability_score,
)

_RV_CSS = """
<style>
[class^="rv-"], [class^="rv-"] * {
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
.rv-metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.55rem;
    margin-bottom: 0.72rem;
}
.rv-metric-card {
    border: 1px solid #E4E0D8;
    background: #FBF8F1;
    border-radius: 8px;
    padding: 0.70rem 0.92rem;
    min-height: 112px;
    display: grid;
    grid-template-columns: 3px 1fr;
    gap: 0.75rem;
}
.rv-metric-accent {
    width: 3px;
    border-radius: 999px;
    min-height: 100%;
}
.rv-metric-content {
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.rv-metric-label {
    color: var(--etf-ink-muted);
    font-size: 0.60rem;
    text-transform: uppercase;
    letter-spacing: 0.38px;
    margin-bottom: 0.28rem;
    font-weight: 700;
}
.rv-metric-value {
    font-size: 0.96rem;
    font-weight: 700;
    line-height: 1.08;
    color: var(--etf-ink);
    margin-bottom: 0.48rem;
    text-transform: uppercase;
}
.rv-metric-sub {
    color: #8D8779;
    font-size: 0.58rem;
    text-transform: uppercase;
    letter-spacing: 0.24px;
    margin-bottom: 0.06rem;
}
.rv-metric-sub-value {
    color: var(--etf-ink);
    font-size: 0.76rem;
    font-weight: 700;
    line-height: 1.1;
}
.rv-chart-panel {
    border: 1px solid #E4E0D8;
    background: #FBF8F1;
    border-radius: 8px;
    padding: 0.60rem 0.75rem 0.35rem 0.75rem;
    margin-bottom: 0.75rem;
}
.rv-chart-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.8rem;
    margin-bottom: 0.3rem;
    flex-wrap: wrap;
}
.rv-chart-title {
    color: var(--etf-ink);
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.28px;
}
.rv-chart-controls {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
    margin-left: auto;
}
div[role="radiogroup"] {
    display: flex !important;
    gap: 0 !important;
    flex-wrap: nowrap !important;
    border: 1px solid var(--etf-border) !important;
    border-radius: 4px !important;
    overflow: hidden !important;
    background: #FBF8F1 !important;
}
div[role="radiogroup"] label[data-baseweb="radio"] {
    margin: 0 !important;
    padding: 0.28rem 0.75rem !important;
    min-height: 30px !important;
    border: none !important;
    border-right: 1px solid var(--etf-border) !important;
    background: #FBF8F1 !important;
    display: flex !important;
    align-items: center !important;
}
div[role="radiogroup"] label[data-baseweb="radio"]:last-child {
    border-right: none !important;
}
div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child {
    display: none !important;
}
div[role="radiogroup"] label[data-baseweb="radio"] > div:last-child {
    margin-left: 0 !important;
}
div[role="radiogroup"] label[data-baseweb="radio"] p {
    margin: 0 !important;
    color: var(--etf-ink-muted) !important;
    font-size: 0.62rem !important;
    font-weight: 700 !important;
    line-height: 1 !important;
    text-transform: uppercase;
    letter-spacing: 0.28px !important;
}
div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
    background: rgba(111,123,70,0.08) !important;
    border-color: var(--etf-accent) !important;
}
div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) p {
    color: var(--etf-accent) !important;
}
.rv-col-panel {
    border: 1px solid #E4E0D8;
    background: #FBF8F1;
    border-radius: 8px;
    padding: 0.62rem 0.76rem;
    min-height: 100%;
}
.rv-col-title {
    color: #8D8779;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.42px;
    font-weight: 700;
    margin-bottom: 0.34rem;
    border-bottom: 1px solid var(--etf-border);
    padding-bottom: 0.22rem;
}
.rv-col-row {
    display: flex;
    justify-content: space-between;
    padding: 0.15rem 0;
    border-bottom: 1px solid rgba(216,212,199,0.5);
}
.rv-col-row:last-child { border-bottom: none; }
.rv-col-key {
    color: var(--etf-ink-muted);
    font-size: 0.60rem;
    text-transform: uppercase;
    letter-spacing: 0.22px;
}
.rv-col-val {
    color: var(--etf-ink);
    font-size: 0.68rem;
    font-weight: 700;
}
.rv-col-framework-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.35rem;
    padding: 0.16rem 0;
    border-bottom: 1px solid rgba(216,212,199,0.5);
}
.rv-col-framework-row:last-child { border-bottom: none; }
.rv-col-zone {
    color: var(--etf-ink-muted);
    font-size: 0.60rem;
    text-transform: uppercase;
    letter-spacing: 0.20px;
}
.rv-col-action {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
}
.rv-action-entry { color: var(--etf-up); }
.rv-action-exit { color: #C4882A; }
.rv-action-stop { color: #C97C6B; }
.rv-link {
    text-align: center;
    color: #8D8779;
    font-size: 0.68rem;
    font-weight: 700;
    margin-top: 0.45rem;
    text-transform: uppercase;
    letter-spacing: 0.26px;
}
</style>
"""


@st.cache_data(ttl=300, show_spinner=False)
def _cached_screener_rows(
    cache_key: str,
    selected_security: str,
    candidate_tickers: tuple[str, ...],
    rv_start_date: str,
    rv_end_date: str,
    _security_history: pd.DataFrame,
    _candidate_histories: dict[str, pd.DataFrame],
):
    """Cache the expensive pair-stat recomputation across reruns for the same window."""
    screener_rows = []
    base_security = ETF(selected_security)
    base_security.set_history(_security_history)

    for candidate in candidate_tickers:
        candidate_hist = _candidate_histories.get(candidate, pd.DataFrame())
        if candidate_hist.empty:
            continue

        candidate_security = ETF(candidate)
        candidate_security.set_history(candidate_hist)
        candidate_merged = filtered_prices(
            base_security,
            candidate_security,
            start_date=pd.Timestamp(rv_start_date),
            end_date=pd.Timestamp(rv_end_date),
        )
        if len(candidate_merged) < 10:
            continue
        spread_frame, spread_diagnostics = diagnose_spread(
            candidate_merged,
            left_ticker=base_security.ticker,
            right_ticker=candidate_security.ticker,
            spread_kind="return",
            beta_source="trailing",
            beta_lookback=60,
            hedge_window=60,
            z_window=20,
        )
        beta_60d, _, _ = beta_metrics(
            base_security,
            candidate_security,
            start_date=pd.Timestamp(rv_start_date),
            end_date=pd.Timestamp(rv_end_date),
        )
        corr_60d_series = rolling_correlation(base_security, candidate_security, window=60).dropna()
        corr_60d = float(corr_60d_series.iloc[-1]) if not corr_60d_series.empty else 0.0
        spread_mean = spread_frame["spread_mean"].dropna()
        spread_last = spread_frame["spread"].dropna()
        spread_dev = (
            (float(spread_last.iloc[-1]) - float(spread_mean.iloc[-1])) * 100.0
            if not spread_last.empty and not spread_mean.empty
            else 0.0
        )
        regime = regime_from_zscore(spread_diagnostics.zscore_last)
        fwd_10_ret, _, _ = forward_spread_reversion_stats(spread_frame, 10)
        fwd_20_ret, _, _ = forward_spread_reversion_stats(spread_frame, 20)
        action = _action_label(spread_diagnostics.zscore_last)
        screener_rows.append(
            {
                "PAIR": SpreadDefinition(base_security.ticker, candidate_security.ticker).name,
                "Z-SCORE": spread_diagnostics.zscore_last,
                "SPREAD DEV": spread_dev,
                "BETA (60D)": beta_60d,
                "CORR (60D)": corr_60d,
                "HALF-LIFE": spread_diagnostics.half_life_days or 0.0,
                "REGIME": regime.replace(" / EXTREME", ""),
                "FWD 10D RET": fwd_10_ret,
                "FWD 20D RET": fwd_20_ret,
                "ACTION": _pill_badge(action),
            }
        )

    return pd.DataFrame(screener_rows)


def _action_label(z: float) -> str:
    """Map a z-score to a lean screener action."""
    if abs(z) >= 1.0:
        return "WATCH"
    return "HOLD"


def _pill_badge(label: str) -> str:
    """Return an outlined pill badge HTML string."""
    styles = {
        "WATCH": "color:#C4882A;border:1px solid rgba(196,136,42,0.45);background:rgba(196,136,42,0.06);",
        "HOLD": "color:#6B6560;border:1px solid rgba(141,135,121,0.40);background:rgba(141,135,121,0.05);",
    }
    style = styles.get(label, styles["HOLD"])
    return (
        f"<span style='display:inline-flex;align-items:center;justify-content:center;"
        f"min-width:56px;padding:0.18rem 0.42rem;border-radius:999px;font-size:0.58rem;"
        f"font-weight:700;letter-spacing:0.22px;text-transform:uppercase;{style}'>{label}</span>"
    )


class RVTab:
    """Render pair-trading and relative-value analytics for the selected ETF."""

    def __init__(self, price_store):
        self.price_store = price_store
        self.table = DashboardTable()
        self.controls = DashboardControls()

    def _metric_card_html(
        self,
        label: str,
        value: str,
        sub: str = "",
        *,
        value_color: str = "var(--etf-ink)",
    ) -> str:
        """Return HTML for a single RV metric card."""
        accent = value_color if value_color.startswith("var(") else value_color
        sub_block = ""
        if sub:
            title, _, detail = sub.partition("|")
            sub_block = (
                f"<div class='rv-metric-sub'>{title}</div>"
                f"<div class='rv-metric-sub-value'>{detail or title}</div>"
            )
        return (
            f"<div class='rv-metric-card'>"
            f"<div class='rv-metric-accent' style='background:{accent};'></div>"
            f"<div class='rv-metric-content'>"
            f"<div class='rv-metric-label'>{label}</div>"
            f"<div class='rv-metric-value' style='color:{value_color};'>{value}</div>"
            f"{sub_block}"
            f"</div>"
            f"</div>"
        )

    def _rv_signal(self, current_z: float) -> str:
        """Return the compact signal label used in the KPI strip."""
        if current_z >= 1.0:
            return "RICH"
        if current_z <= -1.0:
            return "CHEAP"
        return "NEUTRAL"

    def _volume_multiple(self, history: pd.DataFrame) -> float | None:
        """Return latest volume divided by the 30-day average."""
        if history.empty or "volume" not in history.columns:
            return None
        volume = history["volume"].astype(float)
        avg = volume.rolling(30, min_periods=5).mean().iloc[-1]
        current = volume.iloc[-1]
        if pd.isna(current) or pd.isna(avg) or avg == 0:
            return None
        return float(current / avg)

    def _render_top_cards(
        self,
        rv_regime: str,
        current_z: float,
        stability: float,
        abs_dev_pct: float,
        fwd_20_avg: float,
        fwd_20_hit: float,
        fwd_20_n: int,
        fair_value: float,
    ) -> None:
        """Render the 4 top metric cards: RV SIGNAL / REGIME / DISLOCATION / FWD RETURN 20D."""
        signal_label = self._rv_signal(current_z)
        signal_color = (
            "var(--etf-down)"
            if signal_label == "RICH"
            else "var(--etf-up)" if signal_label == "CHEAP" else "var(--etf-ink)"
        )
        regime_color = "#C4882A"
        disloc_color = "var(--etf-down)" if abs_dev_pct >= 0 else "var(--etf-up)"
        fwd_color = "var(--etf-up)" if fwd_20_avg >= 0 else "var(--etf-down)"
        cards = "".join(
            [
                self._metric_card_html(
                    "RV Signal", signal_label, f"Z-Score|{current_z:.2f}", value_color=signal_color
                ),
                self._metric_card_html(
                    "Regime",
                    rv_regime.replace(" / EXTREME", ""),
                    f"Stability|{stability:.0f} / 100",
                    value_color=regime_color,
                ),
                self._metric_card_html(
                    "Dislocation",
                    f"{abs_dev_pct:+.2f}%",
                    f"Fair Value (20D)|{fair_value:+.2f}%",
                    value_color=disloc_color,
                ),
                self._metric_card_html(
                    "Fwd Return (20D)",
                    f"{fwd_20_avg:+.2f}%",
                    f"Hit Rate|{fwd_20_hit:.0%} ({int(round(fwd_20_hit * fwd_20_n))}/{fwd_20_n})",
                    value_color=fwd_color,
                ),
            ]
        )
        st.markdown(f"<div class='rv-metric-grid'>{cards}</div>", unsafe_allow_html=True)

    def _render_three_columns(
        self,
        current_beta: float,
        current_credit_beta: float | None,
        current_equity_beta: float | None,
        r_squared: float,
        residual_5d: float,
        current_z: float,
        abs_dev_pct: float,
        beta_60d: float,
        current_corr_60: float,
        half_life: float,
        stability: float,
        adf_pvalue: float | None,
        adf_is_stationary: bool | None,
        left_liquidity: float | None,
        right_liquidity: float | None,
    ) -> None:
        """Render FACTOR EXPOSURES / PAIR METRICS / TRADING FRAMEWORK as three side-by-side panels."""
        c1, c2, c3 = st.columns(3)

        with c1:
            rows = [
                ("Rates Beta (5Y)", f"{current_beta:,.2f}"),
                (
                    "Credit Beta (HY OAS)",
                    "--" if current_credit_beta is None else f"{current_credit_beta:,.2f}",
                ),
                (
                    "Equity Beta (SPY)",
                    "--" if current_equity_beta is None else f"{current_equity_beta:,.2f}",
                ),
                ("R²", f"{r_squared:,.2f}"),
                ("Residual (5D Avg)", f"{residual_5d:,.2f}%"),
            ]
            cells = "".join(
                f"<div class='rv-col-row'>"
                f"<span class='rv-col-key'>{k}</span>"
                f"<span class='rv-col-val'>{v}</span>"
                f"</div>"
                for k, v in rows
            )
            st.markdown(
                f"<div class='rv-col-panel'>"
                f"<div class='rv-col-title'>Factor Exposures (Daily)</div>"
                f"{cells}</div>",
                unsafe_allow_html=True,
            )

        with c2:
            rows = [
                ("Z-Score", f"{current_z:+.2f}"),
                ("Spread Dev", f"{abs_dev_pct:+.2f}%"),
                ("Rolling Beta (60D)", f"{beta_60d:,.2f}"),
                ("Correlation (60D)", f"{current_corr_60:,.2f}"),
                ("Half-Life", f"{half_life:,.1f}d" if half_life > 0 else "N/A"),
                ("Stability", f"{stability:,.0f} / 100"),
                ("ADF p-value", self._format_adf_pvalue(adf_pvalue, adf_is_stationary)),
                (
                    "Liquidity",
                    (
                        f"{left_liquidity:.2f}x / {right_liquidity:.2f}x"
                        if left_liquidity is not None and right_liquidity is not None
                        else "--"
                    ),
                ),
            ]
            cells = "".join(
                f"<div class='rv-col-row'>"
                f"<span class='rv-col-key'>{k}</span>"
                f"<span class='rv-col-val'>{v}</span>"
                f"</div>"
                for k, v in rows
            )
            st.markdown(
                f"<div class='rv-col-panel'>"
                f"<div class='rv-col-title'>Pair Metrics</div>"
                f"{cells}</div>",
                unsafe_allow_html=True,
            )

        with c3:
            framework = [
                ("Entry", "|Z| > 2.0", "rv-action-entry"),
                ("Exit", "Z → 0", "rv-action-exit"),
                ("Stop", "|Z| > 3.0", "rv-action-stop"),
            ]
            rows_html = "".join(
                f"<div class='rv-col-framework-row'>"
                f"<span class='rv-col-zone'>{zone}</span>"
                f"<span class='rv-col-action {cls}'>{action}</span>"
                f"</div>"
                for zone, action, cls in framework
            )
            st.markdown(
                f"<div class='rv-col-panel'>"
                f"<div class='rv-col-title'>Trading Framework</div>"
                f"{rows_html}</div>",
                unsafe_allow_html=True,
            )

    def _render_chart_section(
        self, rv_merged: pd.DataFrame, selected_security: str, compare_security: str
    ) -> None:
        """Render the chart section with compact segmented selectors."""
        st.markdown("<div class='rv-chart-panel'>", unsafe_allow_html=True)
        head_left, head_right = st.columns([0.46, 0.54])
        with head_left:
            st.markdown(
                f"<div class='rv-chart-title'>Z-Score ({selected_security} / {compare_security})</div>",
                unsafe_allow_html=True,
            )
        with head_right:
            control_left, control_right = st.columns([0.62, 0.38])
            with control_left:
                chart_type = st.radio(
                    "Chart",
                    ["Z-SCORE", "SPREAD", "BETA-ADJ Z"],
                    horizontal=True,
                    key=f"rv_chart_type_{selected_security}_{compare_security}",
                    label_visibility="collapsed",
                )
            with control_right:
                rv_period = st.radio(
                    "RV Period",
                    ["6M", "1Y", "2Y", "ALL"],
                    horizontal=True,
                    key=f"rv_period_segments_{selected_security}_{compare_security}",
                    label_visibility="collapsed",
                )

        title = ""
        if chart_type == "Z-SCORE":
            render_zscore_chart(
                rv_merged["zscore"], selected_security, compare_security, title=title
            )
        elif chart_type == "SPREAD":
            render_return_spread_chart(
                rv_merged["cum_spread"], selected_security, compare_security, title=title
            )
        else:
            render_beta_adjusted_z_chart(
                rv_merged["beta_adj_z"],
                pd.Series(1.0, index=rv_merged.index),
                selected_security,
                compare_security,
                title=title,
            )
        st.markdown("</div>", unsafe_allow_html=True)
        return rv_period

    def _render_pair_screener(self, screener_df: pd.DataFrame) -> None:
        """Render the RV pair screener in the requested wide table layout."""
        st.markdown(
            "<div style='color:#8D8779;font-size:0.62rem;text-transform:uppercase;"
            "letter-spacing:0.42px;font-weight:700;margin:0.55rem 0 0.25rem 0;'>RV Pair Screener</div>",
            unsafe_allow_html=True,
        )
        if screener_df.empty:
            st.info("No RV screening candidates available for the selected window.")
            return

        screener_df = (
            screener_df.sort_values(by=["Z-SCORE", "SPREAD DEV"], ascending=[False, False])
            .head(12)
            .copy()
        )
        screener_df = self.table.format_screener(screener_df)
        self.table.render(screener_df, hide_index=True)
        st.markdown("<div class='rv-link'>View all pairs →</div>", unsafe_allow_html=True)

    def render(self, security: ETF, tickers) -> None:
        """Render the RV Analysis tab: metric cards, chart, three-column panels, and screener."""
        st.markdown(_RV_CSS, unsafe_allow_html=True)
        st.subheader("RV Analysis")
        hist = security.history
        selected_security = security.ticker

        rv_candidates = [ticker for ticker in tickers if ticker != selected_security]
        compare_col, _ = st.columns([0.32, 0.68])
        with compare_col:
            compare_security = self.controls.render_select(
                "Compare With",
                rv_candidates,
                key=f"rv_compare_{selected_security}",
            )

        compare_obj = ETF(compare_security)
        cache_key = app_cache_key(self.price_store.engine)
        with timed_block("rv.load_compare_history"):
            compare_hist = cached_price_history(
                cache_key, compare_security, None, None, self.price_store
            )
            compare_obj.set_history(compare_hist)
        if compare_hist.empty:
            st.warning(f"No price history found for {compare_security}.")
            return

        merged = (
            hist[["adj_close", "volume"]]
            .join(
                compare_hist[["adj_close", "volume"]],
                how="inner",
                lsuffix="_base",
                rsuffix="_comp",
            )
            .dropna()
        )

        if merged.empty:
            st.warning("No overlapping history available for RV analysis.")
            return

        rv_period = st.session_state.get(
            f"rv_period_segments_{selected_security}_{compare_security}", "6M"
        )
        max_date = merged.index.max()
        min_date = merged.index.min()
        lookback_days = {"6M": 182, "1Y": 365, "2Y": 730}
        rv_start_date = (
            max(min_date, max_date - timedelta(days=lookback_days[rv_period]))
            if rv_period in lookback_days
            else min_date
        )
        rv_end_date = max_date

        merged_dates = pd.to_datetime(merged.index)
        rv_merged = merged.loc[
            (merged_dates >= pd.Timestamp(rv_start_date))
            & (merged_dates <= pd.Timestamp(rv_end_date))
        ].copy()

        if rv_merged.empty:
            st.warning("No overlapping RV history available for the selected dates.")
            return

        corr_60_series = rolling_correlation(security, compare_obj, window=60)
        corr_60_series = corr_60_series.loc[rv_merged.index.intersection(corr_60_series.index)]
        current_corr_60 = (
            float(corr_60_series.dropna().iloc[-1]) if not corr_60_series.dropna().empty else 0.0
        )

        current_beta, beta_adj_spread, beta_adj_z = beta_metrics(
            security,
            compare_obj,
            start_date=rv_start_date,
            end_date=rv_end_date,
        )
        beta_adj_spread = beta_adj_spread.loc[rv_merged.index]
        beta_adj_z = beta_adj_z.loc[rv_merged.index]
        rv_merged["beta_adj_spread"] = beta_adj_spread
        rv_merged["beta_adj_z"] = beta_adj_z if not beta_adj_z.empty else 0.0
        rv_pair_prices = rv_merged[["adj_close_base", "adj_close_comp"]].rename(
            columns={"adj_close_base": "close_left", "adj_close_comp": "close_right"}
        )
        spread_frame, spread_diagnostics = diagnose_spread(
            rv_pair_prices,
            left_ticker=selected_security,
            right_ticker=compare_security,
            spread_kind="return",
            beta_source="trailing",
            beta_lookback=60,
            hedge_window=60,
            z_window=20,
        )
        spread_frame = spread_frame.loc[rv_merged.index]
        rv_merged["zscore"] = spread_frame["zscore"] if not spread_frame.empty else 0.0
        rv_merged["return_spread"] = spread_frame["spread"] if not spread_frame.empty else 0.0

        current_z = float(spread_diagnostics.zscore_last)
        fair_value = (
            float(spread_frame["spread_mean"].dropna().iloc[-1]) * 100.0
            if not spread_frame["spread_mean"].dropna().empty
            else 0.0
        )
        current_spread = (
            float(spread_frame["spread"].dropna().iloc[-1]) * 100.0
            if not spread_frame["spread"].dropna().empty
            else 0.0
        )
        abs_dev_pct = current_spread - fair_value
        half_life = spread_diagnostics.half_life_days or 0.0
        rv_regime = regime_from_zscore(current_z)
        stability = spread_stability_score(spread_diagnostics)

        _, fwd_10_hit, fwd_10_n = forward_spread_reversion_stats(spread_frame, 10)
        fwd_20_avg, fwd_20_hit, fwd_20_n = forward_spread_reversion_stats(spread_frame, 20)

        rv_merged["base_cumret"] = (
            rv_merged["adj_close_base"] / float(rv_merged["adj_close_base"].iloc[0]) - 1.0
        )
        rv_merged["comp_cumret"] = (
            rv_merged["adj_close_comp"] / float(rv_merged["adj_close_comp"].iloc[0]) - 1.0
        )
        rv_merged["cum_spread"] = rv_merged["return_spread"].fillna(0.0).cumsum()

        left_liquidity = self._volume_multiple(hist)
        right_liquidity = self._volume_multiple(compare_hist)
        r_squared = current_corr_60**2
        residual_5d = (
            float(beta_adj_spread.tail(5).mean()) * 100.0
            if not beta_adj_spread.dropna().empty
            else 0.0
        )

        self._render_top_cards(
            rv_regime,
            current_z,
            stability,
            abs_dev_pct,
            fwd_20_avg,
            fwd_20_hit,
            fwd_20_n,
            fair_value,
        )

        selected_period = self._render_chart_section(rv_merged, selected_security, compare_security)
        if selected_period != rv_period:
            st.rerun()

        self._render_three_columns(
            current_beta,
            None,
            None,
            r_squared,
            residual_5d,
            current_z,
            abs_dev_pct,
            current_beta,
            current_corr_60,
            half_life,
            stability,
            spread_diagnostics.adf_pvalue,
            spread_diagnostics.adf_is_stationary_5pct,
            left_liquidity,
            right_liquidity,
        )
        with timed_block("rv.bulk_load_candidate_histories"):
            candidate_histories = cached_multi_price_history(
                cache_key,
                tuple(sorted(rv_candidates)),
                start_date=rv_start_date,
                end_date=rv_end_date,
                _price_store=self.price_store,
            )

        screener_cache_key = (
            f"{cache_key}:"
            f"{selected_security}:{rv_start_date.date()}:{rv_end_date.date()}:"
            f"{max(hist.index).date() if not hist.empty else 'na'}:{len(rv_candidates)}"
        )
        with timed_block("rv.build_pair_screener"):
            screener_df = _cached_screener_rows(
                screener_cache_key,
                selected_security,
                tuple(sorted(rv_candidates)),
                rv_start_date.date().isoformat(),
                rv_end_date.date().isoformat(),
                hist,
                candidate_histories,
            )

        self._render_pair_screener(screener_df)

        with st.expander("Signal History"):
            signal_history = rv_merged[["zscore"]].copy().reset_index()
            signal_labels = signal_history["zscore"].apply(self._signal_regime)
            signal_history["regime"] = signal_labels.map(lambda v: v[0])
            signal_history["cross"] = signal_labels.map(lambda v: v[1])
            signal_history["date"] = signal_history["date"].dt.strftime("%Y-%m-%d")
            signal_history["zscore"] = signal_history["zscore"].map(lambda x: f"{x:,.2f}")
            signal_history = signal_history.rename(
                columns={"date": "DATE", "zscore": "Z-SCORE", "regime": "REGIME", "cross": "CROSS"}
            ).tail(12)
            signal_history = self.table.format_signal_history(signal_history)
            self.table.render(signal_history, hide_index=True)

    def _format_adf_pvalue(self, value: float | None, is_stationary: bool | None) -> str:
        """Format ADF p-value with a concise mean-reversion read."""
        if value is None or is_stationary is None:
            return "--"
        label = "MR" if is_stationary else "No MR"
        return f"{value:.4f} ({label})"

    def _signal_regime(self, z_value: float) -> tuple[str, str]:
        """Map a z-score to a (regime label, threshold label) pair for the signal-history table."""
        if z_value >= 2:
            return "RICH / EXTREME", "+2σ"
        if z_value >= 1:
            return "RICH", "+1σ"
        if z_value <= -2:
            return "CHEAP / EXTREME", "-2σ"
        if z_value <= -1:
            return "CHEAP", "-1σ"
        return "NEUTRAL", ""
