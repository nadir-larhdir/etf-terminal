from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Security:
    """Represent one ETF and expose convenience methods around its stored history."""

    ticker: str
    name: str | None = None
    asset_class: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    history: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def has_history(self) -> bool:
        return not self.history.empty

    @property
    def has_metadata(self) -> bool:
        return bool(self.metadata)

    @property
    def display_name(self) -> str:
        if self.name:
            return f"{self.ticker} — {self.name}"
        return self.ticker

    def set_history(self, history: pd.DataFrame) -> None:
        self.history = history.copy()

    def set_metadata(self, metadata: dict[str, Any] | None) -> None:
        self.metadata = metadata.copy() if metadata else {}

    def load_history(self, price_repo) -> pd.DataFrame:
        self.history = price_repo.get_ticker_price_history(self.ticker)
        return self.history

    def load_metadata(self, metadata_repo) -> dict[str, Any]:
        loaded = metadata_repo.get_ticker_metadata(self.ticker)
        self.metadata = loaded.copy() if loaded else {}
        return self.metadata

    def last_price(self) -> float | None:
        if self.history.empty or "close" not in self.history.columns:
            return None
        return float(self.history["close"].iloc[-1])

    def last_volume(self) -> float | None:
        if self.history.empty or "volume" not in self.history.columns:
            return None
        return float(self.history["volume"].iloc[-1])

    def close_series(self) -> pd.Series:
        if self.history.empty or "close" not in self.history.columns:
            return pd.Series(dtype=float)
        return self.history["close"].copy()

    def volume_series(self) -> pd.Series:
        if self.history.empty or "volume" not in self.history.columns:
            return pd.Series(dtype=float)
        return self.history["volume"].copy()

    def returns(self) -> pd.Series:
        close = self.close_series()
        if close.empty:
            return pd.Series(dtype=float)
        return close.pct_change().dropna()

    def normalized_price(self, base: float = 100.0) -> pd.Series:
        close = self.close_series()
        if close.empty:
            return pd.Series(dtype=float)
        first_value = float(close.iloc[0])
        if first_value == 0:
            return pd.Series(dtype=float, index=close.index)
        return (close / first_value) * base

    def rolling_volume_mean(self, window: int = 30) -> pd.Series:
        volume = self.volume_series()
        if volume.empty:
            return pd.Series(dtype=float)
        return volume.rolling(window).mean()


    def aligned_with(self, other: "Security") -> pd.DataFrame:
        left = self.close_series().rename("close_self")
        right = other.close_series().rename("close_other")
        if left.empty or right.empty:
            return pd.DataFrame(columns=["close_self", "close_other"])
        return pd.concat([left, right], axis=1).dropna()

    def relative_ratio(self, other: "Security") -> pd.Series:
        aligned = self.aligned_with(other)
        if aligned.empty:
            return pd.Series(dtype=float)
        return aligned["close_self"] / aligned["close_other"]

    def ratio_zscore(self, other: "Security", window: int | None = None) -> pd.Series:
        ratio = self.relative_ratio(other)
        if ratio.empty:
            return pd.Series(dtype=float)

        if window is None:
            mean_val = ratio.mean()
            std_val = ratio.std(ddof=0)
            if pd.isna(std_val) or float(std_val) == 0:
                return pd.Series(0.0, index=ratio.index)
            return (ratio - mean_val) / std_val

        rolling_mean = ratio.rolling(window).mean()
        rolling_std = ratio.rolling(window).std(ddof=0)
        z = (ratio - rolling_mean) / rolling_std
        return z.fillna(0.0)

    def rolling_correlation(self, other: "Security", window: int = 20) -> pd.Series:
        own_returns = self.returns()
        other_returns = other.returns()
        if own_returns.empty or other_returns.empty:
            return pd.Series(dtype=float)
        merged = pd.concat(
            [own_returns.rename("ret_self"), other_returns.rename("ret_other")],
            axis=1,
        ).dropna()
        if merged.empty:
            return pd.Series(dtype=float)
        return merged["ret_self"].rolling(window).corr(merged["ret_other"])

    def rolling_beta(self, other: "Security", window: int = 20) -> pd.Series:
        own_returns = self.returns()
        other_returns = other.returns()
        if own_returns.empty or other_returns.empty:
            return pd.Series(dtype=float)
        merged = pd.concat(
            [own_returns.rename("ret_self"), other_returns.rename("ret_other")],
            axis=1,
        ).dropna()
        if merged.empty:
            return pd.Series(dtype=float)
        cov = merged["ret_self"].rolling(window).cov(merged["ret_other"])
        var = merged["ret_other"].rolling(window).var()
        beta = cov / var
        return beta.replace([float("inf"), float("-inf")], pd.NA)

    def beta_adjusted_spread(self, other: "Security", beta: float | None = None) -> pd.Series:
        aligned = self.aligned_with(other)
        if aligned.empty:
            return pd.Series(dtype=float)

        beta_value = beta
        if beta_value is None:
            beta_series = self.rolling_beta(other)
            beta_series = beta_series.dropna()
            beta_value = float(beta_series.iloc[-1]) if not beta_series.empty else 1.0

        return aligned["close_self"] - beta_value * aligned["close_other"]

    def beta_adjusted_zscore(self, other: "Security", beta: float | None = None) -> pd.Series:
        spread = self.beta_adjusted_spread(other, beta=beta)
        if spread.empty:
            return pd.Series(dtype=float)
        mean_val = spread.mean()
        std_val = spread.std(ddof=0)
        if pd.isna(std_val) or float(std_val) == 0:
            return pd.Series(0.0, index=spread.index)
        return (spread - mean_val) / std_val
