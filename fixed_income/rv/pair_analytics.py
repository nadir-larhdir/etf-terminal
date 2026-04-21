from __future__ import annotations

import math

import pandas as pd

from fixed_income.rv.hedge_models import beta_adjusted_spread, beta_adjusted_zscore, beta_stability, latest_beta, rolling_beta
from fixed_income.rv.spread_definition import RVAnalyticsSnapshot, SpreadDefinition


def aligned_prices(left, right) -> pd.DataFrame:
    left_close = left.close_series().rename("close_left")
    right_close = right.close_series().rename("close_right")
    if left_close.empty or right_close.empty:
        return pd.DataFrame(columns=["close_left", "close_right"])
    return pd.concat([left_close, right_close], axis=1).dropna()


def filtered_prices(left, right, *, start_date=None, end_date=None) -> pd.DataFrame:
    aligned = aligned_prices(left, right)
    if aligned.empty:
        return aligned
    aligned_dates = pd.to_datetime(aligned.index)
    if start_date is not None:
        aligned = aligned.loc[aligned_dates >= pd.Timestamp(start_date)]
        aligned_dates = pd.to_datetime(aligned.index)
    if end_date is not None:
        aligned = aligned.loc[aligned_dates <= pd.Timestamp(end_date)]
    return aligned


def returns_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame(columns=["ret_left", "ret_right"])
    returns = prices.pct_change().dropna()
    if returns.empty:
        return pd.DataFrame(columns=["ret_left", "ret_right"])
    return returns.rename(columns={"close_left": "ret_left", "close_right": "ret_right"})


def ratio(left, right, *, start_date=None, end_date=None) -> pd.Series:
    prices = filtered_prices(left, right, start_date=start_date, end_date=end_date)
    if prices.empty:
        return pd.Series(dtype=float)
    return prices["close_left"] / prices["close_right"]


def ratio_zscore(left, right, *, window: int | None = None, start_date=None, end_date=None) -> pd.Series:
    series = ratio(left, right, start_date=start_date, end_date=end_date)
    if series.empty:
        return pd.Series(dtype=float)
    if window is None:
        mean_val = series.mean()
        std_val = series.std(ddof=0)
        if pd.isna(std_val) or float(std_val) == 0:
            return pd.Series(0.0, index=series.index)
        return (series - mean_val) / std_val
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std(ddof=0)
    return ((series - rolling_mean) / rolling_std).fillna(0.0)


def returns_frame(left, right) -> pd.DataFrame:
    left_returns = left.returns().rename("ret_left")
    right_returns = right.returns().rename("ret_right")
    if left_returns.empty or right_returns.empty:
        return pd.DataFrame(columns=["ret_left", "ret_right"])
    return pd.concat([left_returns, right_returns], axis=1).dropna()


def rolling_correlation(left, right, *, window: int = 20) -> pd.Series:
    merged = returns_frame(left, right)
    if merged.empty:
        return pd.Series(dtype=float)
    return merged["ret_left"].rolling(window).corr(merged["ret_right"])


def half_life_proxy(left, right, *, start_date=None, end_date=None) -> float:
    series = ratio(left, right, start_date=start_date, end_date=end_date)
    if len(series) <= 3:
        return 0.0
    lag1_autocorr = float(series.autocorr(lag=1))
    if 0 < lag1_autocorr < 1:
        return float(-math.log(2) / math.log(lag1_autocorr))
    return 0.0


def latest_correlation(left, right, *, window: int = 20) -> float:
    corr_series = rolling_correlation(left, right, window=window).dropna()
    if corr_series.empty:
        return 0.0
    return float(corr_series.iloc[-1])


def stability_score(left, right, *, start_date=None, end_date=None) -> float:
    series = ratio(left, right, start_date=start_date, end_date=end_date)
    ratio_autocorr = float(series.autocorr(lag=1)) if len(series) > 3 else 0.0
    half_life_component = (
        max(min(1 - abs(((-math.log(2) / math.log(ratio_autocorr)) if 0 < ratio_autocorr < 1 else 0.0) - 10) / 20, 1.0), 0.0)
        if 0 < ratio_autocorr < 1
        else 0.0
    )
    corr_component = max(min(abs(latest_correlation(left, right, window=20)), 1.0), 0.0)
    beta_component = max(min(1 / (1 + beta_stability(returns_frame(left, right), window=20)), 1.0), 0.0)
    return 100 * (0.45 * corr_component + 0.30 * half_life_component + 0.25 * beta_component)


def forward_reversion_stats(left, right, horizon: int) -> tuple[float, float, int]:
    series = ratio(left, right)
    zscore = ratio_zscore(left, right)
    if series.empty or zscore.empty:
        return 0.0, 0.0, 0

    event_dates = []
    prev_is_extreme = False
    for dt, z_val in zscore.items():
        is_extreme = abs(float(z_val)) >= 2.0
        if is_extreme and not prev_is_extreme:
            event_dates.append(dt)
        prev_is_extreme = is_extreme

    favorable_moves: list[float] = []
    for dt in event_dates:
        idx = series.index.get_loc(dt)
        if not isinstance(idx, int):
            continue
        future_idx = idx + horizon
        if future_idx >= len(series):
            continue
        start_ratio = float(series.iloc[idx])
        end_ratio = float(series.iloc[future_idx])
        z0 = float(zscore.iloc[idx])
        raw_move = ((end_ratio / start_ratio) - 1.0) * 100 if start_ratio != 0 else 0.0
        favorable_moves.append((-1.0 if z0 > 0 else 1.0) * raw_move)

    if not favorable_moves:
        return 0.0, 0.0, 0
    avg_move = float(sum(favorable_moves) / len(favorable_moves))
    hit_rate = float(sum(1.0 for x in favorable_moves if x > 0) / len(favorable_moves))
    return avg_move, hit_rate, len(favorable_moves)


def latest_ratio(left, right, *, start_date=None, end_date=None) -> float:
    series = ratio(left, right, start_date=start_date, end_date=end_date)
    return 0.0 if series.empty else float(series.iloc[-1])


def latest_zscore(left, right, *, start_date=None, end_date=None) -> float:
    series = ratio_zscore(left, right, start_date=start_date, end_date=end_date)
    return 0.0 if series.empty else float(series.iloc[-1])


def ratio_deviation_pct(left, right, *, start_date=None, end_date=None) -> float:
    series = ratio(left, right, start_date=start_date, end_date=end_date)
    if series.empty:
        return 0.0
    mean_val = float(series.mean())
    current_ratio = float(series.iloc[-1])
    return 0.0 if mean_val == 0 else ((current_ratio / mean_val) - 1.0) * 100


def regime_label(left, right, *, start_date=None, end_date=None) -> str:
    current_z = latest_zscore(left, right, start_date=start_date, end_date=end_date)
    if current_z >= 2.0:
        return "RICH / EXTREME"
    if current_z >= 1.0:
        return "RICH"
    if current_z <= -2.0:
        return "CHEAP / EXTREME"
    if current_z <= -1.0:
        return "CHEAP"
    return "NEUTRAL"


def trade_bias(left, right, *, start_date=None, end_date=None) -> str:
    current_z = latest_zscore(left, right, start_date=start_date, end_date=end_date)
    if current_z >= 2.0:
        return f"Fade rich: Short {left.ticker} / Long {right.ticker}"
    if current_z >= 1.0:
        return f"Monitor richening in {left.ticker} vs {right.ticker}"
    if current_z <= -2.0:
        return f"Fade cheap: Long {left.ticker} / Short {right.ticker}"
    if current_z <= -1.0:
        return f"Monitor cheapening in {left.ticker} vs {right.ticker}"
    return "No strong RV dislocation signal"


def mean_reversion_quality(left, right, *, start_date=None, end_date=None) -> str:
    series = ratio(left, right, start_date=start_date, end_date=end_date)
    if len(series) <= 3:
        return "Weak / Unstable"
    lag1_autocorr = float(series.autocorr(lag=1))
    if 0 < lag1_autocorr < 0.6:
        return "Strong MR"
    if 0.6 <= lag1_autocorr < 0.85:
        return "Moderate MR"
    return "Weak / Unstable"


def window_zscore(left, right, window: int) -> float:
    series = ratio(left, right)
    if series.empty:
        return 0.0
    window_ratio = series.tail(min(window, len(series)))
    if len(window_ratio) <= 1:
        return 0.0
    mean_val = float(window_ratio.mean())
    std_val = float(window_ratio.std(ddof=0))
    return 0.0 if std_val == 0 else (float(window_ratio.iloc[-1]) - mean_val) / std_val


def screener_snapshot(
    definition: SpreadDefinition,
    left,
    right,
    *,
    start_date=None,
    end_date=None,
    prices: pd.DataFrame | None = None,
) -> RVAnalyticsSnapshot:
    prices = filtered_prices(left, right, start_date=start_date, end_date=end_date) if prices is None else prices
    if prices.empty:
        return RVAnalyticsSnapshot(name=definition.name, zscore=0.0, correlation_20d=0.0, stability=0.0)

    series = prices["close_left"] / prices["close_right"]
    if series.empty:
        return RVAnalyticsSnapshot(name=definition.name, zscore=0.0, correlation_20d=0.0, stability=0.0)

    ratio_mean = float(series.mean())
    ratio_std = float(series.std(ddof=0)) if len(series) > 1 else 0.0
    current_ratio = float(series.iloc[-1])
    current_z = ((current_ratio - ratio_mean) / ratio_std) if ratio_std != 0 else 0.0
    returns = returns_from_prices(prices)
    corr_series = returns["ret_left"].rolling(20).corr(returns["ret_right"]).dropna() if not returns.empty else pd.Series(dtype=float)
    current_corr = float(corr_series.iloc[-1]) if not corr_series.empty else 0.0
    ratio_autocorr = float(series.autocorr(lag=1)) if len(series) > 3 else 0.0
    half_life_component = (
        max(min(1 - abs(((-math.log(2) / math.log(ratio_autocorr)) if 0 < ratio_autocorr < 1 else 0.0) - 10) / 20, 1.0), 0.0)
        if 0 < ratio_autocorr < 1
        else 0.0
    )
    corr_component = max(min(abs(current_corr), 1.0), 0.0)
    beta_component = max(min(1 / (1 + beta_stability(returns, window=20)), 1.0), 0.0) if not returns.empty else 0.0
    stability = 100 * (0.45 * corr_component + 0.30 * half_life_component + 0.25 * beta_component)
    return RVAnalyticsSnapshot(
        name=definition.name,
        zscore=round(current_z, 2),
        correlation_20d=round(current_corr, 2),
        stability=round(stability, 0),
    )


def beta_metrics(left, right, *, start_date=None, end_date=None, beta: float | None = None) -> tuple[float, pd.Series, pd.Series]:
    aligned = filtered_prices(left, right, start_date=start_date, end_date=end_date)
    returns = returns_frame(left, right)
    beta_value = beta if beta is not None else latest_beta(returns)
    spread = beta_adjusted_spread(aligned, beta=beta_value) if not aligned.empty else pd.Series(dtype=float)
    zscore = beta_adjusted_zscore(spread) if not spread.empty else pd.Series(dtype=float)
    return beta_value, spread, zscore
