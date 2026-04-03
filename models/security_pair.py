from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from models.security import Security


def _empty_series() -> pd.Series:
    return pd.Series(dtype=float)


@dataclass
class SecurityPair:
    """Model a tradable ETF pair and compute relative-value statistics."""

    left: Security
    right: Security

    @property
    def name(self) -> str:
        return f"{self.left.ticker}/{self.right.ticker}"

    def aligned_prices(self) -> pd.DataFrame:
        left_close = self.left.close_series().rename("close_left")
        right_close = self.right.close_series().rename("close_right")
        if left_close.empty or right_close.empty:
            return pd.DataFrame(columns=["close_left", "close_right"])
        return pd.concat([left_close, right_close], axis=1).dropna()

    def filtered_prices(self, start_date=None, end_date=None) -> pd.DataFrame:
        aligned = self.aligned_prices()
        if aligned.empty:
            return aligned

        aligned_dates = pd.to_datetime(aligned.index)
        if start_date is not None:
            aligned = aligned.loc[aligned_dates >= pd.Timestamp(start_date)]
            aligned_dates = pd.to_datetime(aligned.index)
        if end_date is not None:
            aligned = aligned.loc[aligned_dates <= pd.Timestamp(end_date)]
        return aligned

    def ratio(self, start_date=None, end_date=None) -> pd.Series:
        aligned = self.filtered_prices(start_date=start_date, end_date=end_date)
        if aligned.empty:
            return _empty_series()
        return aligned["close_left"] / aligned["close_right"]

    def ratio_zscore(self, window: int | None = None, start_date=None, end_date=None) -> pd.Series:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        if ratio.empty:
            return _empty_series()

        if window is None:
            mean_val = ratio.mean()
            std_val = ratio.std(ddof=0)
            if pd.isna(std_val) or float(std_val) == 0:
                return pd.Series(0.0, index=ratio.index)
            return (ratio - mean_val) / std_val

        rolling_mean = ratio.rolling(window).mean()
        rolling_std = ratio.rolling(window).std(ddof=0)
        zscore = (ratio - rolling_mean) / rolling_std
        return zscore.fillna(0.0)

    def returns(self) -> pd.DataFrame:
        left_returns = self.left.returns().rename("ret_left")
        right_returns = self.right.returns().rename("ret_right")
        if left_returns.empty or right_returns.empty:
            return pd.DataFrame(columns=["ret_left", "ret_right"])
        return pd.concat([left_returns, right_returns], axis=1).dropna()

    def rolling_correlation(self, window: int = 20) -> pd.Series:
        merged = self.returns()
        if merged.empty:
            return _empty_series()
        return merged["ret_left"].rolling(window).corr(merged["ret_right"])

    def rolling_beta(self, window: int = 20) -> pd.Series:
        merged = self.returns()
        if merged.empty:
            return _empty_series()
        cov = merged["ret_left"].rolling(window).cov(merged["ret_right"])
        var = merged["ret_right"].rolling(window).var()
        beta = cov / var
        return beta.replace([float("inf"), float("-inf")], pd.NA)

    def latest_beta(self, window: int = 20, default: float = 1.0) -> float:
        beta_series = self.rolling_beta(window=window).dropna()
        if beta_series.empty:
            return default
        return float(beta_series.iloc[-1])

    def beta_adjusted_spread(self, beta: float | None = None, start_date=None, end_date=None) -> pd.Series:
        aligned = self.filtered_prices(start_date=start_date, end_date=end_date)
        if aligned.empty:
            return _empty_series()

        beta_value = beta if beta is not None else self.latest_beta()
        return aligned["close_left"] - beta_value * aligned["close_right"]

    def beta_adjusted_zscore(self, beta: float | None = None, start_date=None, end_date=None) -> pd.Series:
        spread = self.beta_adjusted_spread(beta=beta, start_date=start_date, end_date=end_date)
        if spread.empty:
            return _empty_series()
        mean_val = spread.mean()
        std_val = spread.std(ddof=0)
        if pd.isna(std_val) or float(std_val) == 0:
            return pd.Series(0.0, index=spread.index)
        return (spread - mean_val) / std_val

    def half_life_proxy(self, start_date=None, end_date=None) -> float:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        if len(ratio) <= 3:
            return 0.0
        lag1_autocorr = float(ratio.autocorr(lag=1))
        if 0 < lag1_autocorr < 1:
            return float(-math.log(2) / math.log(lag1_autocorr))
        return 0.0

    def beta_stability(self, window: int = 20) -> float:
        beta_series = self.rolling_beta(window=window).dropna()
        if len(beta_series) <= 1:
            return 0.0
        return float(beta_series.std(ddof=0))

    def latest_correlation(self, window: int = 20) -> float:
        corr_series = self.rolling_correlation(window=window).dropna()
        if corr_series.empty:
            return 0.0
        return float(corr_series.iloc[-1])

    def stability_score(self, start_date=None, end_date=None) -> float:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        ratio_autocorr = float(ratio.autocorr(lag=1)) if len(ratio) > 3 else 0.0
        half_life_component = (
            max(min(1 - abs(((-math.log(2) / math.log(ratio_autocorr)) if 0 < ratio_autocorr < 1 else 0.0) - 10) / 20, 1.0), 0.0)
            if 0 < ratio_autocorr < 1
            else 0.0
        )
        corr_component = max(min(abs(self.latest_correlation(window=20)), 1.0), 0.0)
        beta_component = max(min(1 / (1 + self.beta_stability(window=20)), 1.0), 0.0)
        return 100 * (
            0.45 * corr_component
            + 0.30 * half_life_component
            + 0.25 * beta_component
        )

    def forward_reversion_stats(self, horizon: int) -> tuple[float, float, int]:
        ratio = self.ratio()
        zscore = self.ratio_zscore()
        if ratio.empty or zscore.empty:
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
            idx = ratio.index.get_loc(dt)
            if not isinstance(idx, int):
                continue
            future_idx = idx + horizon
            if future_idx >= len(ratio):
                continue

            start_ratio = float(ratio.iloc[idx])
            end_ratio = float(ratio.iloc[future_idx])
            z0 = float(zscore.iloc[idx])
            raw_move = ((end_ratio / start_ratio) - 1.0) * 100 if start_ratio != 0 else 0.0
            favorable_move = (-1.0 if z0 > 0 else 1.0) * raw_move
            favorable_moves.append(favorable_move)

        if not favorable_moves:
            return 0.0, 0.0, 0

        avg_move = float(sum(favorable_moves) / len(favorable_moves))
        hit_rate = float(sum(1.0 for x in favorable_moves if x > 0) / len(favorable_moves))
        return avg_move, hit_rate, len(favorable_moves)

    def screener_row(self, start_date=None, end_date=None) -> dict[str, float | str]:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        if ratio.empty:
            return {
                "PAIR": self.name,
                "Z": 0.0,
                "20D CORR": 0.0,
                "STABILITY": 0.0,
            }

        ratio_mean = float(ratio.mean())
        ratio_std = float(ratio.std(ddof=0)) if len(ratio) > 1 else 0.0
        current_ratio = float(ratio.iloc[-1])
        current_z = ((current_ratio - ratio_mean) / ratio_std) if ratio_std != 0 else 0.0

        corr_series = self.rolling_correlation(window=20).dropna()
        current_corr = float(corr_series.iloc[-1]) if not corr_series.empty else 0.0

        return {
            "PAIR": self.name,
            "Z": round(current_z, 2),
            "20D CORR": round(current_corr, 2),
            "STABILITY": round(self.stability_score(start_date=start_date, end_date=end_date), 0),
        }

    def latest_ratio(self, start_date=None, end_date=None) -> float:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        if ratio.empty:
            return 0.0
        return float(ratio.iloc[-1])

    def latest_zscore(self, start_date=None, end_date=None) -> float:
        zscore = self.ratio_zscore(start_date=start_date, end_date=end_date)
        if zscore.empty:
            return 0.0
        return float(zscore.iloc[-1])

    def ratio_deviation_pct(self, start_date=None, end_date=None) -> float:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        if ratio.empty:
            return 0.0
        mean_val = float(ratio.mean())
        current_ratio = float(ratio.iloc[-1])
        if mean_val == 0:
            return 0.0
        return ((current_ratio / mean_val) - 1.0) * 100

    def regime_label(self, start_date=None, end_date=None) -> str:
        current_z = self.latest_zscore(start_date=start_date, end_date=end_date)
        if current_z >= 2.0:
            return "RICH / EXTREME"
        if current_z >= 1.0:
            return "RICH"
        if current_z <= -2.0:
            return "CHEAP / EXTREME"
        if current_z <= -1.0:
            return "CHEAP"
        return "NEUTRAL"

    def trade_bias(self, start_date=None, end_date=None) -> str:
        current_z = self.latest_zscore(start_date=start_date, end_date=end_date)
        if current_z >= 2.0:
            return f"Fade rich: Short {self.left.ticker} / Long {self.right.ticker}"
        if current_z >= 1.0:
            return f"Monitor richening in {self.left.ticker} vs {self.right.ticker}"
        if current_z <= -2.0:
            return f"Fade cheap: Long {self.left.ticker} / Short {self.right.ticker}"
        if current_z <= -1.0:
            return f"Monitor cheapening in {self.left.ticker} vs {self.right.ticker}"
        return "No strong RV dislocation signal"

    def mean_reversion_quality(self, start_date=None, end_date=None) -> str:
        ratio = self.ratio(start_date=start_date, end_date=end_date)
        if len(ratio) <= 3:
            return "Weak / Unstable"
        lag1_autocorr = float(ratio.autocorr(lag=1))
        if 0 < lag1_autocorr < 0.6:
            return "Strong MR"
        if 0.6 <= lag1_autocorr < 0.85:
            return "Moderate MR"
        return "Weak / Unstable"

    def window_zscore(self, window: int) -> float:
        ratio = self.ratio()
        if ratio.empty:
            return 0.0
        window_ratio = ratio.tail(min(window, len(ratio)))
        if len(window_ratio) <= 1:
            return 0.0
        mean_val = float(window_ratio.mean())
        std_val = float(window_ratio.std(ddof=0))
        if std_val == 0:
            return 0.0
        return (float(window_ratio.iloc[-1]) - mean_val) / std_val
