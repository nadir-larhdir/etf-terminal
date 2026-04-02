import math
from typing import cast
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


class RVTab:
    def __init__(self, price_repo):
        self.price_repo = price_repo
        self.context_panel = ContextPanel()
        self.table = BloombergTable()
        self.controls = BloombergControls()

    def _compute_window_z(self, series: pd.Series, window: int) -> float:
        window_series = series.tail(min(window, len(series)))
        if len(window_series) <= 1:
            return 0.0
        mean_val = float(window_series.mean())
        std_val = float(window_series.std(ddof=0))
        return ((float(window_series.iloc[-1]) - mean_val) / std_val) if std_val != 0 else 0.0

    def _compute_forward_reversion_stats(
        self,
        full_ratio: pd.Series,
        full_z_series: pd.Series,
        horizon: int,
    ) -> tuple[float, float, int]:
        event_dates: list[object] = []
        prev_is_extreme = False
        for dt, z_val in full_z_series.items():
            is_extreme = abs(float(z_val)) >= 2.0
            if is_extreme and not prev_is_extreme:
                event_dates.append(dt)
            prev_is_extreme = is_extreme

        favorable_moves: list[float] = []
        for dt in event_dates:
            if dt not in full_ratio.index:
                continue
            idx = full_ratio.index.get_loc(dt)
            if not isinstance(idx, int):
                continue
            future_idx = idx + horizon
            if future_idx >= len(full_ratio):
                continue
            start_ratio = cast(float, full_ratio.iat[idx])
            end_ratio = cast(float, full_ratio.iat[future_idx])
            z0 = cast(float, full_z_series.iat[idx])
            raw_move = ((end_ratio / start_ratio) - 1.0) * 100 if start_ratio != 0 else 0.0
            favorable_move = (-1.0 if z0 > 0 else 1.0) * raw_move
            favorable_moves.append(favorable_move)

        if not favorable_moves:
            return 0.0, 0.0, 0

        avg_move = sum(favorable_moves) / len(favorable_moves)
        hit_rate = sum(1.0 for x in favorable_moves if x > 0) / len(favorable_moves)
        return avg_move, hit_rate, len(favorable_moves)

    def _render_metric_grid(self, metrics, columns: int) -> None:
        cols = st.columns(columns)
        for idx, (label, value) in enumerate(metrics):
            with cols[idx % columns]:
                st.metric(label, value)



    def _render_pair_screener(
        self,
        rv_candidates,
        hist: pd.DataFrame,
        rv_start_date,
        rv_end_date,
        selected_security: str,
    ) -> None:
        screener_rows = []
        for candidate in rv_candidates:
            candidate_hist = self.price_repo.get_price_history(candidate)
            if candidate_hist.empty:
                continue

            candidate_merged = hist[["close"]].join(
                candidate_hist[["close"]],
                how="inner",
                lsuffix="_base",
                rsuffix="_comp",
            ).dropna()
            candidate_dates = pd.to_datetime(candidate_merged.index)
            candidate_merged = candidate_merged.loc[
                (candidate_dates >= pd.Timestamp(rv_start_date)) & (candidate_dates <= pd.Timestamp(rv_end_date))
            ].copy()
            if len(candidate_merged) < 10:
                continue

            candidate_merged["ratio"] = candidate_merged["close_base"] / candidate_merged["close_comp"]
            cand_ratio_mean = float(candidate_merged["ratio"].mean())
            cand_ratio_std = float(candidate_merged["ratio"].std(ddof=0)) if len(candidate_merged) > 1 else 0.0
            cand_z = ((float(candidate_merged["ratio"].iloc[-1]) - cand_ratio_mean) / cand_ratio_std) if cand_ratio_std != 0 else 0.0

            cand_ret_base = candidate_merged["close_base"].pct_change()
            cand_ret_comp = candidate_merged["close_comp"].pct_change()
            corr_series = cand_ret_base.rolling(20).corr(cand_ret_comp).dropna()
            cand_corr = float(corr_series.iloc[-1]) if not corr_series.empty else 0.0
            cand_beta_series = cand_ret_base.rolling(20).cov(cand_ret_comp) / cand_ret_comp.rolling(20).var()
            cand_beta_stability = float(cand_beta_series.dropna().std(ddof=0)) if len(cand_beta_series.dropna()) > 1 else 0.0
            cand_ratio_autocorr = float(candidate_merged["ratio"].autocorr(lag=1)) if len(candidate_merged) > 3 else 0.0
            cand_half_life_component = (
                max(min(1 - abs(((-math.log(2) / math.log(cand_ratio_autocorr)) if 0 < cand_ratio_autocorr < 1 else 0.0) - 10) / 20, 1.0), 0.0)
                if 0 < cand_ratio_autocorr < 1
                else 0.0
            )
            cand_stability = 100 * (
                0.45 * max(min(abs(cand_corr), 1.0), 0.0)
                + 0.30 * cand_half_life_component
                + 0.25 * max(min(1 / (1 + cand_beta_stability), 1.0), 0.0)
            )

            screener_rows.append(
                {
                    "PAIR": f"{selected_security}/{candidate}",
                    "Z": round(cand_z, 2),
                    "20D CORR": round(cand_corr, 2),
                    "STABILITY": round(cand_stability, 0),
                }
            )

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

    def render(self, hist: pd.DataFrame, tickers, selected_security: str) -> None:
        st.subheader("RV Analysis")

        rv_candidates = [ticker for ticker in tickers if ticker != selected_security]
        compare_security = self.controls.render_select(
            "Compare With",
            rv_candidates,
            key=f"rv_compare_{selected_security}",
        )

        compare_hist = self.price_repo.get_price_history(compare_security)
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

        rv_merged["ratio"] = rv_merged["close_base"] / rv_merged["close_comp"]
        ratio_mean = float(rv_merged["ratio"].mean())
        ratio_std = float(rv_merged["ratio"].std(ddof=0)) if len(rv_merged) > 1 else 0.0
        rv_merged["zscore"] = (rv_merged["ratio"] - ratio_mean) / ratio_std if ratio_std != 0 else 0.0

        current_ratio = float(rv_merged["ratio"].iloc[-1])
        current_z = float(rv_merged["zscore"].iloc[-1])
        abs_dev_pct = ((current_ratio / ratio_mean) - 1.0) * 100 if ratio_mean != 0 else 0.0

        returns_base = rv_merged["close_base"].pct_change()
        returns_comp = rv_merged["close_comp"].pct_change()
        ratio_returns = rv_merged["ratio"].pct_change()

        corr_20_series = returns_base.rolling(20).corr(returns_comp)
        corr_60_series = returns_base.rolling(60).corr(returns_comp)
        current_corr_20 = float(corr_20_series.dropna().iloc[-1]) if not corr_20_series.dropna().empty else 0.0
        current_corr_60 = float(corr_60_series.dropna().iloc[-1]) if not corr_60_series.dropna().empty else 0.0

        beta_series = returns_base.rolling(20).cov(returns_comp) / returns_comp.rolling(20).var()
        if not beta_series.dropna().empty:
            current_beta = float(beta_series.dropna().iloc[-1])
            beta_stability = float(beta_series.dropna().std(ddof=0)) if len(beta_series.dropna()) > 1 else 0.0
        else:
            comp_var = float(returns_comp.var(ddof=0)) if len(returns_comp.dropna()) > 1 else 0.0
            current_beta = float(returns_base.cov(returns_comp) / comp_var) if comp_var != 0 else 1.0
            beta_stability = 0.0

        realized_vol = float(ratio_returns.std(ddof=0)) * (252 ** 0.5) if len(ratio_returns.dropna()) > 1 else 0.0
        vol_adj_score = current_z / realized_vol if realized_vol != 0 else 0.0

        lag1_autocorr = float(rv_merged["ratio"].autocorr(lag=1)) if len(rv_merged) > 3 else 0.0
        half_life = -math.log(2) / math.log(lag1_autocorr) if 0 < lag1_autocorr < 1 else 0.0

        if current_z >= 2.0:
            rv_regime = "RICH / EXTREME"
            trade_bias = f"Fade rich: Short {selected_security} / Long {compare_security}"
        elif current_z >= 1.0:
            rv_regime = "RICH"
            trade_bias = f"Monitor richening in {selected_security} vs {compare_security}"
        elif current_z <= -2.0:
            rv_regime = "CHEAP / EXTREME"
            trade_bias = f"Fade cheap: Long {selected_security} / Short {compare_security}"
        elif current_z <= -1.0:
            rv_regime = "CHEAP"
            trade_bias = f"Monitor cheapening in {selected_security} vs {compare_security}"
        else:
            rv_regime = "NEUTRAL"
            trade_bias = "No strong RV dislocation signal"

        if 0 < lag1_autocorr < 0.6:
            mr_quality = "Strong MR"
        elif 0.6 <= lag1_autocorr < 0.85:
            mr_quality = "Moderate MR"
        else:
            mr_quality = "Weak / Unstable"

        base_vol_ratio = (float(hist["volume"].iloc[-1]) / float(hist["volume"].tail(30).mean())) if float(hist["volume"].tail(30).mean()) != 0 else 0.0
        comp_vol_ratio = (float(compare_hist["volume"].iloc[-1]) / float(compare_hist["volume"].tail(30).mean())) if float(compare_hist["volume"].tail(30).mean()) != 0 else 0.0

        full_ratio = merged["close_base"] / merged["close_comp"]
        z_30d = self._compute_window_z(full_ratio, 30)
        z_90d = self._compute_window_z(full_ratio, 90)
        z_180d = self._compute_window_z(full_ratio, 180)

        rv_merged["beta_adj_spread"] = rv_merged["close_base"] - current_beta * rv_merged["close_comp"]
        spread_mean = float(rv_merged["beta_adj_spread"].mean())
        spread_std = float(rv_merged["beta_adj_spread"].std(ddof=0)) if len(rv_merged) > 1 else 0.0
        rv_merged["beta_adj_z"] = (rv_merged["beta_adj_spread"] - spread_mean) / spread_std if spread_std != 0 else 0.0
        current_beta_adj_z = float(rv_merged["beta_adj_z"].iloc[-1])

        corr_component = max(min((abs(current_corr_20) + abs(current_corr_60)) / 2, 1.0), 0.0)
        hl_component = max(min(1 - abs(half_life - 10) / 20, 1.0), 0.0) if half_life > 0 else 0.0
        beta_component = max(min(1 / (1 + beta_stability), 1.0), 0.0)
        stability_score = 100 * (0.45 * corr_component + 0.30 * hl_component + 0.25 * beta_component)

        full_ratio_mean = float(full_ratio.mean())
        full_ratio_std = float(full_ratio.std(ddof=0)) if len(full_ratio) > 1 else 0.0
        full_z_series = (full_ratio - full_ratio_mean) / full_ratio_std if full_ratio_std != 0 else pd.Series(0.0, index=full_ratio.index)

        fwd_5_avg, fwd_5_hit, fwd_5_n = self._compute_forward_reversion_stats(full_ratio, full_z_series, 5)
        fwd_10_avg, fwd_10_hit, fwd_10_n = self._compute_forward_reversion_stats(full_ratio, full_z_series, 10)
        fwd_20_avg, fwd_20_hit, fwd_20_n = self._compute_forward_reversion_stats(full_ratio, full_z_series, 20)

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

        self._render_pair_screener(rv_candidates, hist, rv_start_date, rv_end_date, selected_security)

        with st.expander("Show RV signal history"):
            signal_history = self.table.format_signal_history(signal_history)
            self.table.render(signal_history, hide_index=True)