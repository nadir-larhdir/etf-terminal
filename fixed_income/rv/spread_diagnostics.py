"""Diagnostics for beta-hedged ETF pair spreads."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from fixed_income import series as ts
from fixed_income.rv.signals import SignalRegime

if TYPE_CHECKING:
    from stores.protocols import PriceHistoryReader

try:
    from statsmodels.tsa.stattools import adfuller
except Exception:  # pragma: no cover - optional dependency
    adfuller = None


TRADING_DAYS = 252


@dataclass(frozen=True)
class SpreadDiagnostics:
    """Lean summary of the key mean-reversion properties of one pair spread."""

    pair: str
    spread_kind: str
    beta: float
    beta_source: str
    sample_start: str
    sample_end: str
    observations: int
    spread_last: float
    spread_mean: float
    spread_std: float
    zscore_last: float
    lag1_autocorr: float | None
    half_life_days: float | None
    half_life_5d_cum_days: float | None
    half_life_zscore_days: float | None
    hurst_exponent: float | None
    zero_crossings: int
    zero_crossings_per_year: float | None
    adf_stat: float | None
    adf_pvalue: float | None
    adf_is_stationary_5pct: bool | None

    def as_dict(self) -> dict[str, object]:
        """Return the diagnostics as a plain dictionary."""
        return asdict(self)


def regime_from_zscore(zscore: float) -> str:
    """Map a z-score to its relative-value regime label."""
    return SignalRegime.from_zscore(zscore).label


def load_pair_prices(
    price_store: PriceHistoryReader,
    left_ticker: str,
    right_ticker: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    price_col: str = "adj_close",
) -> pd.DataFrame:
    """Return aligned price history for one ETF pair."""
    histories = price_store.get_multi_ticker_price_history(
        [left_ticker, right_ticker], start_date=start_date, end_date=end_date
    )
    left = histories.get(left_ticker)
    right = histories.get(right_ticker)
    if left is None or right is None or left.empty or right.empty:
        return pd.DataFrame(columns=["close_left", "close_right"])
    prices = pd.DataFrame(
        {
            "close_left": left[price_col].rename(left_ticker),
            "close_right": right[price_col].rename(right_ticker),
        }
    ).dropna()
    prices.index = pd.to_datetime(prices.index)
    return prices.sort_index()


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Return aligned daily log returns for a two-column price frame."""
    if prices.empty:
        return pd.DataFrame(columns=["ret_left", "ret_right"])
    returns = ts.log_returns(prices)
    return returns.rename(columns={"close_left": "ret_left", "close_right": "ret_right"})


def rolling_beta(returns: pd.DataFrame, window: int = 60) -> pd.Series:
    """Return rolling OLS beta of left returns on right returns."""
    return ts.RollingWindow(window).beta(returns["ret_left"], returns["ret_right"])


def estimate_beta(
    prices: pd.DataFrame,
    *,
    lookback: int | None = None,
    source: str = "trailing",
    default: float = 1.0,
) -> float:
    """Estimate a static hedge beta from aligned pair prices."""
    returns = log_returns(prices)
    if returns.empty:
        return default
    sample = returns if source == "full_sample" else returns.tail(lookback or len(returns))
    return ts.beta(sample["ret_left"], sample["ret_right"], default=default)


def build_spread_frame(
    prices: pd.DataFrame,
    *,
    beta: float,
    spread_kind: str = "price",
    hedge_window: int = 60,
    z_window: int = 20,
) -> pd.DataFrame:
    """Build one analysis frame with prices, returns, spread, z-score, and rolling beta."""
    if prices.empty:
        return pd.DataFrame(
            columns=[
                "close_left",
                "close_right",
                "ret_left",
                "ret_right",
                "rolling_beta",
                "spread",
                "spread_change",
                "spread_mean",
                "spread_std",
                "zscore",
            ]
        )

    returns = log_returns(prices)
    frame = prices.join(returns, how="left")
    frame["rolling_beta"] = rolling_beta(returns, window=hedge_window).reindex(frame.index)
    if spread_kind == "return":
        frame["spread"] = frame["ret_left"] - beta * frame["ret_right"]
    else:
        frame["spread"] = frame["close_left"] - beta * frame["close_right"]
    rolling = ts.RollingWindow(z_window)
    frame["spread_change"] = frame["spread"].diff()
    frame["spread_mean"] = rolling.mean(frame["spread"])
    frame["spread_std"] = rolling.std(frame["spread"])
    frame["zscore"] = rolling.zscore(frame["spread"])
    return frame


def lag1_autocorr(series: pd.Series) -> float | None:
    """Return lag-1 autocorrelation or None when the series is too short."""
    clean = series.dropna()
    if len(clean) < 3:
        return None
    value = clean.autocorr(lag=1)
    return None if pd.isna(value) else float(value)


def half_life(series: pd.Series) -> float | None:
    """Estimate OU-style half-life from the beta-hedged spread."""
    clean = series.dropna()
    if len(clean) < 20:
        return None
    lagged = clean.shift(1).dropna()
    delta = clean.diff().dropna()
    aligned = pd.concat([lagged.rename("lagged"), delta.rename("delta")], axis=1).dropna()
    if aligned.empty:
        return None
    slope, _ = np.polyfit(aligned["lagged"], aligned["delta"], 1)
    if pd.isna(slope) or slope >= 0:
        return None
    estimate = -math.log(2) / slope
    # A trending spread fits a slope of roughly -0, which produces an astronomically large
    # half-life rather than a useful one. Reversion slower than the sample is not evidence
    # of reversion at all, so report it as undefined.
    if not math.isfinite(estimate) or estimate > len(clean):
        return None
    return float(estimate)


def cumulative_spread(series: pd.Series, window: int = 5) -> pd.Series:
    """Return a rolling cumulative spread over the given window."""
    return ts.RollingWindow(window).sum(series)


def hurst_exponent(series: pd.Series, max_lag: int = 20) -> float | None:
    """Estimate the Hurst exponent with a simple log-log lag regression."""
    clean = series.dropna().astype(float)
    if len(clean) < max(40, max_lag + 2):
        return None
    lags = range(2, max_lag + 1)
    tau = [clean.diff(lag).dropna().std(ddof=0) for lag in lags]
    points = [(lag, val) for lag, val in zip(lags, tau, strict=False) if val and val > 0]
    if len(points) < 5:
        return None
    log_lags = np.log([lag for lag, _ in points])
    log_tau = np.log([val for _, val in points])
    slope, _ = np.polyfit(log_lags, log_tau, 1)
    return float(slope)


def zero_crossings(series: pd.Series) -> int:
    """Count how often the demeaned spread crosses zero."""
    clean = series.dropna()
    if len(clean) < 2:
        return 0
    # A spread that lands exactly on the mean is neither side of it; carrying the previous
    # sign forward keeps that day from hiding the crossing that surrounds it.
    signs = np.sign(clean - clean.mean()).replace(0, np.nan).ffill().dropna()
    return int((signs * signs.shift(1) < 0).sum())


def adf_diagnostics(series: pd.Series) -> tuple[float | None, float | None, bool | None]:
    """Return ADF stat, p-value, and a 5% stationarity flag when statsmodels is available."""
    clean = series.dropna()
    if adfuller is None or len(clean) < 20:
        return None, None, None
    stat, pvalue, *_ = adfuller(clean, autolag="AIC")
    return float(stat), float(pvalue), bool(pvalue < 0.05)


def spread_stability_score(diagnostics: SpreadDiagnostics) -> float:
    """Return a compact 0-100 stability score for one spread diagnostics snapshot."""
    adf_component = 1.0 if diagnostics.adf_is_stationary_5pct else 0.25
    half_life_component = 0.0
    if diagnostics.half_life_days is not None and diagnostics.half_life_days > 0:
        half_life_component = max(min(1.0 - abs(diagnostics.half_life_days - 5.0) / 20.0, 1.0), 0.0)
    crossing_component = 0.0
    if diagnostics.zero_crossings_per_year is not None:
        crossing_component = max(min(diagnostics.zero_crossings_per_year / 100.0, 1.0), 0.0)
    score = 100.0 * (0.45 * adf_component + 0.35 * half_life_component + 0.20 * crossing_component)
    return round(score, 0)


def forward_spread_reversion_stats(
    frame: pd.DataFrame, horizon: int, *, threshold: float = 2.0
) -> tuple[float, float, int]:
    """Return avg favorable forward move, hit rate, and count after |z| threshold breaches."""
    if frame.empty:
        return 0.0, 0.0, 0
    subset = frame[["spread", "zscore"]].dropna().copy()
    if subset.empty:
        return 0.0, 0.0, 0
    subset["fwd_spread"] = subset["spread"].rolling(horizon).sum().shift(-horizon + 1)

    event_dates: list[pd.Timestamp] = []
    prev_is_extreme = False
    for dt, z_val in subset["zscore"].items():
        is_extreme = abs(float(z_val)) >= threshold
        if is_extreme and not prev_is_extreme:
            event_dates.append(pd.Timestamp(dt))  # type: ignore[arg-type]
        prev_is_extreme = is_extreme

    favorable_moves: list[float] = []
    for dt in event_dates:
        if dt not in subset.index:
            continue
        z0 = float(subset.at[dt, "zscore"])  # type: ignore[arg-type]
        fwd = subset.at[dt, "fwd_spread"]
        if pd.isna(fwd):
            continue
        favorable_moves.append((-1.0 if z0 > 0 else 1.0) * float(fwd) * 100.0)  # type: ignore[arg-type]

    if not favorable_moves:
        return 0.0, 0.0, 0
    avg_move = float(sum(favorable_moves) / len(favorable_moves))
    hit_rate = float(sum(1.0 for x in favorable_moves if x > 0) / len(favorable_moves))
    return avg_move, hit_rate, len(favorable_moves)


def breach_events(
    frame: pd.DataFrame,
    threshold: float,
    *,
    signal_col: str = "zscore",
    payoff_col: str = "spread",
) -> pd.DataFrame:
    """Return first-breach event rows for one threshold on the chosen signal column."""
    subset = frame[[payoff_col, signal_col, "rolling_beta"]].dropna().copy()
    if subset.empty:
        return pd.DataFrame(columns=[payoff_col, signal_col, "rolling_beta"])
    is_extreme = subset[signal_col].abs() >= threshold
    first_breach = is_extreme & ~is_extreme.shift(1, fill_value=False)
    return subset.loc[first_breach].copy()


def event_study(
    frame: pd.DataFrame,
    *,
    thresholds: tuple[float, ...] = (1.5, 2.0, 2.5),
    horizons: tuple[int, ...] = (1, 3, 5, 10),
    round_trip_cost: float = 0.0,
    beta_drift_horizon: int = 5,
    signal_col: str = "zscore",
    payoff_col: str = "spread",
) -> pd.DataFrame:
    """Return an event-study table for first-breach z-score signals."""
    if frame.empty:
        return pd.DataFrame()

    base = frame[[payoff_col, signal_col, "rolling_beta"]].dropna().copy()
    if base.empty:
        return pd.DataFrame()

    sample_years = len(base) / TRADING_DAYS if len(base) else 0.0
    rows: list[dict[str, float | int]] = []

    for threshold in thresholds:
        events = breach_events(base, threshold, signal_col=signal_col, payoff_col=payoff_col)
        if events.empty:
            continue

        event_metrics: dict[int, pd.Series] = {}
        for horizon in horizons:
            event_metrics[horizon] = (
                base[payoff_col].rolling(horizon).sum().shift(-horizon + 1).reindex(events.index)
            )

        beta_drift = (
            base["rolling_beta"].shift(-beta_drift_horizon).reindex(events.index)
            - events["rolling_beta"]
        ).abs()
        beta_entry_std_20d = base["rolling_beta"].rolling(20).std(ddof=0).reindex(events.index)

        for horizon in horizons:
            signed_fwd = np.where(
                events[signal_col] > 0,
                -event_metrics[horizon],
                event_metrics[horizon],
            )
            valid = pd.Series(signed_fwd, index=events.index).dropna()
            if valid.empty:
                continue
            rows.append(
                {
                    "threshold": threshold,
                    "horizon_d": horizon,
                    "n_events": int(len(valid)),
                    "events_per_year": (
                        0.0 if sample_years == 0 else float(len(valid) / sample_years)
                    ),
                    "avg_fwd_bps": float(valid.mean() * 10000.0),
                    "median_fwd_bps": float(valid.median() * 10000.0),
                    "hit_rate": float((valid > 0).mean()),
                    "net_avg_bps": float((valid.mean() - round_trip_cost) * 10000.0),
                    "net_hit_rate": float(((valid - round_trip_cost) > 0).mean()),
                    "avg_entry_beta": float(events.loc[valid.index, "rolling_beta"].mean()),
                    "entry_beta_std": float(events.loc[valid.index, "rolling_beta"].std(ddof=0)),
                    "avg_beta_20d_std": float(beta_entry_std_20d.loc[valid.index].mean()),
                    "avg_abs_beta_drift_5d": float(beta_drift.loc[valid.index].mean()),
                }
            )

    return pd.DataFrame(rows)


def diagnose_spread(
    prices: pd.DataFrame,
    *,
    left_ticker: str,
    right_ticker: str,
    spread_kind: str = "price",
    beta_source: str = "trailing",
    beta_lookback: int = 60,
    hedge_window: int = 60,
    z_window: int = 20,
) -> tuple[pd.DataFrame, SpreadDiagnostics]:
    """Return the analysis frame plus a lean diagnostics summary for one pair."""
    beta = estimate_beta(
        prices,
        lookback=beta_lookback if beta_source == "trailing" else None,
        source=beta_source,
    )
    frame = build_spread_frame(
        prices,
        beta=beta,
        spread_kind=spread_kind,
        hedge_window=hedge_window,
        z_window=z_window,
    )
    spread = frame["spread"].dropna()
    zscore = frame["zscore"].dropna()
    adf_stat, adf_pvalue, stationary = adf_diagnostics(spread)
    crossing_count = zero_crossings(spread)
    years = len(spread) / TRADING_DAYS if len(spread) else 0.0
    diagnostics = SpreadDiagnostics(
        pair=f"{left_ticker} / {right_ticker}",
        spread_kind=spread_kind,
        beta=round(beta, 4),
        beta_source=beta_source,
        sample_start=spread.index.min().strftime("%Y-%m-%d") if not spread.empty else "",
        sample_end=spread.index.max().strftime("%Y-%m-%d") if not spread.empty else "",
        observations=int(len(spread)),
        spread_last=0.0 if spread.empty else float(spread.iloc[-1]),
        spread_mean=0.0 if spread.empty else float(spread.mean()),
        spread_std=0.0 if spread.empty else float(spread.std(ddof=0)),
        zscore_last=0.0 if zscore.empty else float(zscore.iloc[-1]),
        lag1_autocorr=lag1_autocorr(spread),
        half_life_days=half_life(spread),
        half_life_5d_cum_days=half_life(cumulative_spread(spread, window=5)),
        half_life_zscore_days=half_life(zscore),
        hurst_exponent=hurst_exponent(spread),
        zero_crossings=crossing_count,
        zero_crossings_per_year=None if years == 0 else float(crossing_count / years),
        adf_stat=adf_stat,
        adf_pvalue=adf_pvalue,
        adf_is_stationary_5pct=stationary,
    )
    return frame, diagnostics
