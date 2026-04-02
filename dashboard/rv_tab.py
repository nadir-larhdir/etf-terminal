import pandas as pd
import streamlit as st

from dashboard.context_panel import ContextPanel
from dashboard.table_styles import BloombergTable
from dashboard.controls import BloombergControls
from dashboard.charts import (
    compute_default_date_range,
    render_zscore_chart,
    render_return_spread_chart,
    render_beta_adjusted_z_chart,
)
from models.security import Security
from models.security_pair import SecurityPair


class RVTab:
    def __init__(self, price_repo):
        self.price_repo = price_repo
        self.context_panel = ContextPanel()
        self.table = BloombergTable()
        self.controls = BloombergControls()



    def _render_metric_grid(self, metrics, columns: int) -> None:
        cols = st.columns(columns)
        for idx, (label, value) in enumerate(metrics):
            with cols[idx % columns]:
                st.metric(label, value)



    def _render_pair_screener(
        self,
        rv_candidates,
        security: Security,
        rv_start_date,
        rv_end_date,
        selected_security: str,
    ) -> None:
        screener_rows = []
        for candidate in rv_candidates:
            candidate_obj = Security(candidate)
            candidate_hist = candidate_obj.load_history(self.price_repo)
            if candidate_hist.empty:
                continue

            pair = SecurityPair(security, candidate_obj)
            candidate_merged = pair.filtered_prices(start_date=rv_start_date, end_date=rv_end_date)
            if len(candidate_merged) < 10:
                continue

            screener_rows.append(pair.screener_row(start_date=rv_start_date, end_date=rv_end_date))

        with st.expander("Show RV pair screener"):
            if screener_rows:
                screener_df = pd.DataFrame(screener_rows).sort_values(
                    by=["Z", "STABILITY"],
                    ascending=[False, False],
                ).head(12)
                screener_df = self.table.format_screener(screener_df)
                self.table.render(screener_df, hide_index=True)
            else:
                st.info("No RV screening candidates available for the selected window.")

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
        compare_hist = compare_obj.load_history(self.price_repo)
        if compare_hist.empty:
            st.warning(f"No price history found for {compare_security}.")
            return

        pair = SecurityPair(security, compare_obj)

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

        ratio_series = pair.ratio(start_date=rv_start_date, end_date=rv_end_date)
        ratio_series = ratio_series.loc[rv_merged.index]
        rv_merged["ratio"] = ratio_series
        ratio_mean = float(rv_merged["ratio"].mean())
        ratio_std = float(rv_merged["ratio"].std(ddof=0)) if len(rv_merged) > 1 else 0.0

        zscore_series = pair.ratio_zscore(start_date=rv_start_date, end_date=rv_end_date)
        zscore_series = zscore_series.loc[rv_merged.index]
        rv_merged["zscore"] = zscore_series if not zscore_series.empty else 0.0

        current_ratio = float(rv_merged["ratio"].iloc[-1])
        current_z = float(rv_merged["zscore"].iloc[-1])
        abs_dev_pct = pair.ratio_deviation_pct(start_date=rv_start_date, end_date=rv_end_date)

        ratio_returns = rv_merged["ratio"].pct_change()

        corr_20_series = pair.rolling_correlation(window=20)
        corr_20_series = corr_20_series.loc[rv_merged.index.intersection(corr_20_series.index)]
        current_corr_20 = float(corr_20_series.dropna().iloc[-1]) if not corr_20_series.dropna().empty else 0.0

        corr_60_series = pair.rolling_correlation(window=60)
        corr_60_series = corr_60_series.loc[rv_merged.index.intersection(corr_60_series.index)]
        current_corr_60 = float(corr_60_series.dropna().iloc[-1]) if not corr_60_series.dropna().empty else 0.0

        beta_series = pair.rolling_beta(window=20)
        beta_series = beta_series.loc[rv_merged.index.intersection(beta_series.index)]
        if not beta_series.dropna().empty:
            current_beta = float(beta_series.dropna().iloc[-1])
            beta_stability = float(beta_series.dropna().std(ddof=0)) if len(beta_series.dropna()) > 1 else 0.0
        else:
            current_beta = 1.0
            beta_stability = 0.0

        realized_vol = float(ratio_returns.std(ddof=0)) * (252 ** 0.5) if len(ratio_returns.dropna()) > 1 else 0.0
        vol_adj_score = current_z / realized_vol if realized_vol != 0 else 0.0

        lag1_autocorr = float(rv_merged["ratio"].autocorr(lag=1)) if len(rv_merged) > 3 else 0.0
        half_life = pair.half_life_proxy(start_date=rv_start_date, end_date=rv_end_date)

        rv_regime = pair.regime_label(start_date=rv_start_date, end_date=rv_end_date)
        trade_bias = pair.trade_bias(start_date=rv_start_date, end_date=rv_end_date)

        mr_quality = pair.mean_reversion_quality(start_date=rv_start_date, end_date=rv_end_date)

        base_vol_ratio = (float(hist["volume"].iloc[-1]) / float(hist["volume"].tail(30).mean())) if float(hist["volume"].tail(30).mean()) != 0 else 0.0
        comp_vol_ratio = (float(compare_hist["volume"].iloc[-1]) / float(compare_hist["volume"].tail(30).mean())) if float(compare_hist["volume"].tail(30).mean()) != 0 else 0.0

        z_30d = pair.window_zscore(30)
        z_90d = pair.window_zscore(90)
        z_180d = pair.window_zscore(180)

        beta_adj_spread = pair.beta_adjusted_spread(beta=current_beta, start_date=rv_start_date, end_date=rv_end_date)
        beta_adj_spread = beta_adj_spread.loc[rv_merged.index]
        rv_merged["beta_adj_spread"] = beta_adj_spread

        beta_adj_z = pair.beta_adjusted_zscore(beta=current_beta, start_date=rv_start_date, end_date=rv_end_date)
        beta_adj_z = beta_adj_z.loc[rv_merged.index]
        rv_merged["beta_adj_z"] = beta_adj_z if not beta_adj_z.empty else 0.0
        current_beta_adj_z = float(rv_merged["beta_adj_z"].iloc[-1])

        stability_score = pair.stability_score(start_date=rv_start_date, end_date=rv_end_date)

        fwd_5_avg, fwd_5_hit, fwd_5_n = pair.forward_reversion_stats(5)
        fwd_10_avg, fwd_10_hit, fwd_10_n = pair.forward_reversion_stats(10)
        fwd_20_avg, fwd_20_hit, fwd_20_n = pair.forward_reversion_stats(20)

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
        self._render_metric_grid(
            [
                ("ROLLING BETA", f"{current_beta:,.2f}"),
                ("BETA-ADJ Z", f"{current_beta_adj_z:,.2f}"),
                ("VOL-ADJ SCORE", f"{vol_adj_score:,.2f}"),
                ("HALF-LIFE", f"{half_life:,.1f}d" if half_life > 0 else "N/A"),
                ("STABILITY", f"{stability_score:,.0f}/100"),
                ("MR QUALITY", mr_quality),
            ],
            3,
        )
        self._render_metric_grid(
            [
                ("30D Z", f"{z_30d:,.2f}"),
                ("90D Z", f"{z_90d:,.2f}"),
                ("180D Z", f"{z_180d:,.2f}"),
                ("LIQUIDITY", f"{base_vol_ratio:.2f}x / {comp_vol_ratio:.2f}x"),
                ("BETA STABILITY", f"{beta_stability:,.2f}"),
            ],
            3,
        )

        self.context_panel.render(
            title="RV Signal",
            headline=trade_bias,
            body=rv_signal_paragraph,
            footer=(
                "RV modules active: ratio z-score, return spread, rolling correlation, rolling beta, "
                "regime labels, half-life proxy, vol-adjusted score, window comparison, liquidity overlay, "
                "signal history, beta-adjusted z-score, forward reversion stats, stability score, and pair screener."
            ),
        )

        self.context_panel.render(
            title="Entry / Exit Framework",
            headline="Mean-reversion trading framework",
            body=(
                "Enter mean-reversion trades when the displayed-window z-score moves beyond ±2.0. "
                "Consider trimming risk as the signal re-enters the ±1.0 zone, and treat a move back near 0.0 "
                "as a take-profit / exit region. If the z-score extends beyond ±3.0 or pair correlation "
                "deteriorates sharply, reassess the trade as a potential stop / invalidation scenario."
            ),
            footer=f"Current read: <span style='color:#F3F0E8; font-weight:700;'>{trade_bias}</span>",
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

        render_zscore_chart(rv_merged["zscore"], selected_security, compare_security)

        render_return_spread_chart(rv_merged["cum_spread"], selected_security, compare_security)

        render_beta_adjusted_z_chart(
            rv_merged["beta_adj_z"],
            pd.Series(1.0, index=rv_merged.index),
            selected_security,
            compare_security,
        )

        signal_history = rv_merged[["zscore"]].copy().reset_index()
        signal_history["regime"] = signal_history["zscore"].apply(
            lambda z: "RICH / EXTREME" if z >= 2 else (
                "RICH" if z >= 1 else (
                    "CHEAP / EXTREME" if z <= -2 else (
                        "CHEAP" if z <= -1 else "NEUTRAL"
                    )
                )
            )
        )
        signal_history["cross"] = signal_history["zscore"].apply(
            lambda z: "+2σ" if z >= 2 else (
                "+1σ" if z >= 1 else (
                    "-2σ" if z <= -2 else (
                        "-1σ" if z <= -1 else ""
                    )
                )
            )
        )
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

        self._render_pair_screener(rv_candidates, security, rv_start_date, rv_end_date, selected_security)

        with st.expander("Show RV signal history"):
            signal_history = self.table.format_signal_history(signal_history)
            self.table.render(signal_history, hide_index=True)