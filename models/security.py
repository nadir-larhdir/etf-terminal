from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


def _empty_series() -> pd.Series:
    return pd.Series(dtype=float)


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

    def set_history(self, history: pd.DataFrame) -> None:
        self.history = history.copy()

    def set_metadata(self, metadata: dict[str, Any] | None) -> None:
        self.metadata = metadata.copy() if metadata else {}

    def load_history(self, price_store) -> pd.DataFrame:
        self.history = price_store.get_ticker_price_history(self.ticker)
        return self.history

    def load_metadata(self, metadata_store) -> dict[str, Any]:
        loaded = metadata_store.get_ticker_metadata(self.ticker)
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
            return _empty_series()
        return self.history["close"].copy()

    def volume_series(self) -> pd.Series:
        if self.history.empty or "volume" not in self.history.columns:
            return _empty_series()
        return self.history["volume"].copy()

    def returns(self) -> pd.Series:
        close = self.close_series()
        if close.empty:
            return _empty_series()
        return close.pct_change().dropna()

    def normalized_price(self, base: float = 100.0) -> pd.Series:
        close = self.close_series()
        if close.empty:
            return _empty_series()
        first_value = float(close.iloc[0])
        if first_value == 0:
            return pd.Series(dtype=float, index=close.index)
        return (close / first_value) * base

    def rolling_volume_mean(self, window: int = 30) -> pd.Series:
        volume = self.volume_series()
        if volume.empty:
            return _empty_series()
        return volume.rolling(window).mean()
