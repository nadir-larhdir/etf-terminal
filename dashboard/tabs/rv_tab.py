import pandas as pd
import streamlit as st

from dashboard.cache import app_cache_key, cached_multi_price_history, cached_price_history
from dashboard.components.charts import (
    compute_default_date_range,
    render_beta_adjusted_z_chart,
    render_return_spread_chart,
    render_zscore_chart,
)
from dashboard.components.controls import DashboardControls
from dashboard.components.info_panel import InfoPanel
from dashboard.perf import timed_block
from dashboard.styles.table_styles import DashboardTable
from fixed_income.instruments.security import Security
from fixed_income.rv.hedge_models import beta_stability as hedge_beta_stability
from fixed_income.rv.pair_analytics import (
    beta_metrics,
    filtered_prices,
    forward_reversion_stats,
    half_life_proxy,
    mean_reversion_quality,
    ratio,
    ratio_deviation_pct,
    ratio_zscore,
    regime_label,
    returns_frame,
    rolling_correlation,
    screener_snapshot,
    stability_score,
    trade_bias,
    window_zscore,
)
from fixed_income.rv.spread_definition import SpreadDefinition


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
    base_security = Security(selected_security)
    base_security.set_history(_security_history)

    for candidate in candidate_tickers:
        candidate_hist = _candidate_histories.get(candidate, pd.DataFrame())
        if candidate_hist.empty:
            continue

        candidate_security = Security(candidate)
        candidate_security.set_history(candidate_hist)
        candidate_merged = filtered_prices(
            base_security,
            candidate_security,
            start_date=pd.Timestamp(rv_start_date),
            end_date=pd.Timestamp(rv_end_date),
        )
        if len(candidate_merged) < 10:
            continue
        snapshot = screener_snapshot(
            SpreadDefinition(base_security.ticker, candidate_security.ticker),
            base_security,
            candidate_security,
            start_date=pd.Timestamp(rv_start_date),
            end_date=pd.Timestamp(rv_end_date),
            prices=candidate_merged,
        )
        screener_rows.append(
            {
                "PAIR": snapshot.name,
                "Z": snapshot.zscore,
                "CORR_20D": snapshot.correlation_20d,
                "STABILITY": snapshot.stability,
            }
        )

    return pd.DataFrame(screener_rows)


class RVTab:
    """Render pair-trading and relative-value analytics for the selected ETF."""

    def __init__(self, price_store):
        self.price_store = price_store
        self.info_panel = InfoPanel()
        self.table = DashboardTable()
        self.controls = DashboardControls()

    def _render_metric_grid(self, metrics, columns: int) -> None:
        cols = st.columns(columns)
        for idx, (label, value) in enumerate(metrics):
            with cols[idx % columns]:
                st.metric(label, value)

    def _render_pair_screener(self, screener_df: pd.DataFrame) -> None:
        with st.expander("Show RV pair screener"):
            if not screener_df.empty:
                screener_df = screener_df.sort_values(
                    by=["Z", "STABILITY"],
                    ascending=[False, False],
                ).head(12)
                screener_df = self.table.format_screener(screener_df)
                self.table.render(screener_df, hide_index=True)
            else:
                st.info("No RV screening candidates available for the selected window.")

    def _signal_regime(self, z_value: float) -> tuple[str, str]:
        if z_value >= 2:
            return "RICH / EXTREME", "+2σ"
        if z_value >= 1:
            return "RICH", "+1σ"
        if z_value <= -2:
            return "CHEAP / EXTREME", "-2σ"
        if z_value <= -1:
            return "CHEAP", "-1σ"
        return "NEUTRAL", ""

    def render(self, security: Security, tickers) -> None:
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

        compare_obj = Security(compare_security)
        cache_key = app_cache_key(self.price_store.engine)
        with timed_block("rv.load_compare_history"):
            compare_hist = cached_price_history(cache_key, compare_security, None, None, self.price_store)
            compare_obj.set_history(compare_hist)
        if compare_hist.empty:
            st.warning(f"No price history found for {compare_security}.")
            return

        merged = hist[["close", "volume"]].join(
            compare_hist[["close", "volume"]],
            how="inner",
            lsuffix="_base",
            rsuffix="_comp",
        ).dropna()

        if merged.empty:
            st.warning("No overlapping history available for RV analysis.")
            return

        default_rv_period = "6M"
        rv_default_start, rv_default_end = compute_default_date_range(merged, default_rv_period)

        rv_period, rv_start_date, rv_end_date = self.controls.render_window_and_dates(
            window_label="RV Window",
            window_options=["5D", "30D", "3M", "6M", "1Y"],
            window_index=3,
            window_key=f"rv_period_{selected_security}_{compare_security}",
            start_label="RV Start Date",
            end_label="RV End Date",
            default_start=rv_default_start,
            default_end=rv_default_end,
            min_date=merged.index.min().date(),
            max_date=merged.index.max().date(),
            start_key=f"rv_start_{selected_security}_{compare_security}_{default_rv_period}",
            end_key=f"rv_end_{selected_security}_{compare_security}_{default_rv_period}",
        )

        merged_dates = pd.to_datetime(merged.index)
        rv_merged = merged.loc[
            (merged_dates >= pd.Timestamp(rv_start_date)) & (merged_dates <= pd.Timestamp(rv_end_date))
        ].copy()

        if rv_merged.empty:
            st.warning("No overlapping RV history available for the selected dates.")
            return

        ratio_series = ratio(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)
        ratio_series = ratio_series.loc[rv_merged.index]
        rv_merged["ratio"] = ratio_series
        ratio_mean = float(rv_merged["ratio"].mean())
        ratio_std = float(rv_merged["ratio"].std(ddof=0)) if len(rv_merged) > 1 else 0.0

        zscore_series = ratio_zscore(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)
        zscore_series = zscore_series.loc[rv_merged.index]
        rv_merged["zscore"] = zscore_series if not zscore_series.empty else 0.0

        current_ratio = float(rv_merged["ratio"].iloc[-1])
        current_z = float(rv_merged["zscore"].iloc[-1])
        abs_dev_pct = ratio_deviation_pct(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)

        ratio_returns = rv_merged["ratio"].pct_change()

        corr_20_series = rolling_correlation(security, compare_obj, window=20)
        corr_20_series = corr_20_series.loc[rv_merged.index.intersection(corr_20_series.index)]
        current_corr_20 = float(corr_20_series.dropna().iloc[-1]) if not corr_20_series.dropna().empty else 0.0

        corr_60_series = rolling_correlation(security, compare_obj, window=60)
        corr_60_series = corr_60_series.loc[rv_merged.index.intersection(corr_60_series.index)]
        current_corr_60 = float(corr_60_series.dropna().iloc[-1]) if not corr_60_series.dropna().empty else 0.0

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
        current_beta_adj_z = float(rv_merged["beta_adj_z"].iloc[-1])
        beta_stability_value = hedge_beta_stability(returns_frame(security, compare_obj), window=20)

        realized_vol = float(ratio_returns.std(ddof=0)) * (252 ** 0.5) if len(ratio_returns.dropna()) > 1 else 0.0
        vol_adj_score = current_z / realized_vol if realized_vol != 0 else 0.0

        lag1_autocorr = float(rv_merged["ratio"].autocorr(lag=1)) if len(rv_merged) > 3 else 0.0
        half_life = half_life_proxy(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)

        rv_regime = regime_label(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)
        trade_bias_label = trade_bias(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)

        mr_quality = mean_reversion_quality(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)

        base_vol_ratio = (float(hist["volume"].iloc[-1]) / float(hist["volume"].tail(30).mean())) if float(hist["volume"].tail(30).mean()) != 0 else 0.0
        comp_vol_ratio = (float(compare_hist["volume"].iloc[-1]) / float(compare_hist["volume"].tail(30).mean())) if float(compare_hist["volume"].tail(30).mean()) != 0 else 0.0

        z_30d = window_zscore(security, compare_obj, 30)
        z_90d = window_zscore(security, compare_obj, 90)
        z_180d = window_zscore(security, compare_obj, 180)

        stability = stability_score(security, compare_obj, start_date=rv_start_date, end_date=rv_end_date)

        fwd_5_avg, fwd_5_hit, fwd_5_n = forward_reversion_stats(security, compare_obj, 5)
        fwd_10_avg, fwd_10_hit, fwd_10_n = forward_reversion_stats(security, compare_obj, 10)
        fwd_20_avg, fwd_20_hit, fwd_20_n = forward_reversion_stats(security, compare_obj, 20)

        if abs(current_z) >= 2.0:
            stretch_comment = (
                f"The pair is statistically stretched with a z-score of {current_z:,.2f} and a ratio deviation of {abs_dev_pct:+.2f}% versus its selected-window mean."
            )
        elif abs(current_z) >= 1.0:
            stretch_comment = (
                f"The pair is moving away from fair value with a moderate dislocation: z-score {current_z:,.2f} and ratio deviation {abs_dev_pct:+.2f}%."
            )
        else:
            stretch_comment = (
                f"The pair remains broadly close to its recent equilibrium with a z-score of {current_z:,.2f} and a ratio deviation of {abs_dev_pct:+.2f}%."
            )

        correlation_comment = (
            f"Short-term and medium-term co-movement remains at {current_corr_20:,.2f} and {current_corr_60:,.2f} respectively, while the rolling hedge ratio is {current_beta:,.2f}."
        )

        if half_life > 0:
            mr_comment = (
                f"Mean-reversion quality is assessed as {mr_quality.lower()} with an estimated half-life of {half_life:,.1f} trading days."
            )
        else:
            mr_comment = (
                f"Mean-reversion quality is assessed as {mr_quality.lower()}, but the half-life estimate is not stable enough to be informative on this window."
            )

        liquidity_comment = (
            f"Liquidity conditions are {base_vol_ratio:.2f}x and {comp_vol_ratio:.2f}x of 30-day average volume for {selected_security} and {compare_security}, suggesting the pair is {'reasonably tradeable' if min(base_vol_ratio, comp_vol_ratio) >= 0.8 else 'less balanced from an execution perspective'}."
        )

        horizon_comment = (
            f"Across horizons, the pair screens at {z_30d:,.2f} on 30D, {z_90d:,.2f} on 90D, and {z_180d:,.2f} on 180D, which helps frame whether the current move is tactical or persistent."
        )

        rv_signal_paragraph = " ".join(
            [
                stretch_comment,
                correlation_comment,
                mr_comment,
                liquidity_comment,
                horizon_comment,
            ]
        )

        rv_merged["base_cumret"] = rv_merged["close_base"] / float(rv_merged["close_base"].iloc[0]) - 1.0
        rv_merged["comp_cumret"] = rv_merged["close_comp"] / float(rv_merged["close_comp"].iloc[0]) - 1.0
        rv_merged["cum_spread"] = rv_merged["base_cumret"] - current_beta * rv_merged["comp_cumret"]

        st.caption(f"Displaying RV analysis from {rv_start_date.date()} to {rv_end_date.date()}")
        st.markdown("<div style='margin-bottom:0.35rem;'></div>", unsafe_allow_html=True)

        self._render_metric_grid(
            [
                ("PAIR", f"{selected_security}/{compare_security}"),
                ("Z-SCORE", f"{current_z:,.2f}"),
                ("REGIME", rv_regime),
                ("RATIO DEV", f"{abs_dev_pct:+.2f}%"),
                ("20D CORR", f"{current_corr_20:,.2f}"),
                ("60D CORR", f"{current_corr_60:,.2f}"),
            ],
            3,
        )
        st.markdown("<div class='bb-metric-group-spacer'></div>", unsafe_allow_html=True)
        self._render_metric_grid(
            [
                ("ROLLING BETA", f"{current_beta:,.2f}"),
                ("BETA-ADJ Z", f"{current_beta_adj_z:,.2f}"),
                ("VOL-ADJ SCORE", f"{vol_adj_score:,.2f}"),
                ("HALF-LIFE", f"{half_life:,.1f}d" if half_life > 0 else "N/A"),
                ("STABILITY", f"{stability:,.0f}/100"),
                ("MR QUALITY", mr_quality),
            ],
            3,
        )
        st.markdown("<div class='bb-metric-group-spacer'></div>", unsafe_allow_html=True)
        self._render_metric_grid(
            [
                ("30D Z", f"{z_30d:,.2f}"),
                ("90D Z", f"{z_90d:,.2f}"),
                ("180D Z", f"{z_180d:,.2f}"),
                ("LIQUIDITY", f"{base_vol_ratio:.2f}x / {comp_vol_ratio:.2f}x"),
                ("BETA STABILITY", f"{beta_stability_value:,.2f}"),
            ],
            3,
        )
        st.markdown("<div class='bb-metric-group-spacer'></div>", unsafe_allow_html=True)

        self.info_panel.render(
            title="RV Signal",
            headline=trade_bias_label,
            body=rv_signal_paragraph,
            footer=(
                "RV modules active: ratio z-score, return spread, rolling correlation, rolling beta, "
                "regime labels, half-life proxy, vol-adjusted score, window comparison, liquidity overlay, "
                "signal history, beta-adjusted z-score, forward reversion stats, stability score, and pair screener."
            ),
        )

        self.info_panel.render(
            title="Entry / Exit Framework",
            headline="Mean-reversion trading framework",
            body=(
                "Enter mean-reversion trades when the displayed-window z-score moves beyond ±2.0. "
                "Consider trimming risk as the signal re-enters the ±1.0 zone, and treat a move back near 0.0 "
                "as a take-profit / exit region. If the z-score extends beyond ±3.0 or pair correlation "
                "deteriorates sharply, reassess the trade as a potential stop / invalidation scenario."
            ),
            footer=f"Current read: <span style='color:#F3F0E8; font-weight:700;'>{trade_bias_label}</span>",
            margin_top="0.20rem",
            margin_bottom="0.50rem",
        )

        f1, f2, f3 = st.columns(3)
        with f1:
            st.metric("FWD 5D REV", f"{fwd_5_avg:+.2f}%", f"{fwd_5_hit:.0%} hit | n={fwd_5_n}")
        with f2:
            st.metric("FWD 10D REV", f"{fwd_10_avg:+.2f}%", f"{fwd_10_hit:.0%} hit | n={fwd_10_n}")
        with f3:
            st.metric("FWD 20D REV", f"{fwd_20_avg:+.2f}%", f"{fwd_20_hit:.0%} hit | n={fwd_20_n}")

        st.markdown("<div class='bb-metric-group-spacer'></div>", unsafe_allow_html=True)

        render_zscore_chart(rv_merged["zscore"], selected_security, compare_security)

        render_return_spread_chart(rv_merged["cum_spread"], selected_security, compare_security)

        render_beta_adjusted_z_chart(
            rv_merged["beta_adj_z"],
            pd.Series(1.0, index=rv_merged.index),
            selected_security,
            compare_security,
        )

        signal_history = rv_merged[["zscore"]].copy().reset_index()
        signal_labels = signal_history["zscore"].apply(self._signal_regime)
        signal_history["regime"] = signal_labels.map(lambda value: value[0])
        signal_history["cross"] = signal_labels.map(lambda value: value[1])
        signal_history["date"] = signal_history["date"].dt.strftime("%Y-%m-%d")
        signal_history["zscore"] = signal_history["zscore"].map(lambda x: f"{x:,.2f}")
        signal_history = signal_history.rename(
            columns={
                "date": "DATE",
                "zscore": "Z-SCORE",
                "regime": "REGIME",
                "cross": "CROSS",
            }
        ).tail(12)

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

        with st.expander("Show RV signal history"):
            signal_history = self.table.format_signal_history(signal_history)
            self.table.render(signal_history, hide_index=True)
