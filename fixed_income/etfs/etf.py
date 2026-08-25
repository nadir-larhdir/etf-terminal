from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

from fixed_income import series as ts

if TYPE_CHECKING:
    from stores.protocols import DateLike, MetadataReader, PriceHistoryReader


def _empty_series() -> pd.Series:
    return ts.EMPTY


@dataclass
class ETF:
    """Fixed-income ETF with metadata and historical price helpers."""

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

    def load_history(self, price_store: PriceHistoryReader) -> pd.DataFrame:
        self.history = price_store.get_ticker_price_history(self.ticker)
        return self.history

    def load_metadata(self, metadata_store: MetadataReader) -> dict[str, Any]:
        loaded = metadata_store.get_ticker_metadata(self.ticker)
        self.metadata = loaded.copy() if loaded else {}
        return self.metadata

    def metadata_number(self, key: str) -> float | None:
        """Return a provider metadata field as a float, or None if absent or non-numeric.

        Provider feeds use "", "N/A", and NaN interchangeably for a missing value, so all
        three collapse to None here rather than at each call site.
        """
        raw_value = self.metadata.get(key)
        if raw_value is None or raw_value in ("", "N/A"):
            return None
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        return None if pd.isna(value) else value

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

    def adj_close_series(self) -> pd.Series:
        if self.history.empty:
            return _empty_series()
        column = "adj_close" if "adj_close" in self.history.columns else "close"
        if column not in self.history.columns:
            return _empty_series()
        return self.history[column].copy()

    def volume_series(self) -> pd.Series:
        if self.history.empty or "volume" not in self.history.columns:
            return _empty_series()
        return self.history["volume"].copy()

    def returns(self) -> pd.Series:
        return ts.simple_returns(self.adj_close_series())

    def log_returns(self) -> pd.Series:
        return ts.log_returns(self.adj_close_series())

    def normalized_price(self, base: float = 100.0) -> pd.Series:
        close = self.close_series()
        if close.empty:
            return _empty_series()
        first_value = float(close.iloc[0])
        if first_value == 0:
            return pd.Series(dtype=float, index=close.index)
        return (close / first_value) * base

    def rolling_volume_mean(self, window: int = 30) -> pd.Series:
        return ts.RollingWindow(window).mean(self.volume_series())

    def history_between(self, start_date: DateLike, end_date: DateLike) -> pd.DataFrame:
        if self.history.empty:
            return self.history.copy()
        index = pd.to_datetime(self.history.index)
        filtered = self.history.loc[
            (index >= pd.Timestamp(start_date))  # type: ignore[arg-type]
            & (index <= pd.Timestamp(end_date))  # type: ignore[arg-type]
        ].copy()
        return filtered if not filtered.empty else self.history.tail(1).copy()

    def trading_snapshot(self, volume_window: int = 30) -> dict[str, float | None]:
        if self.history.empty:
            return {
                "latest_price": None,
                "current_volume": None,
                "average_volume": None,
                "volume_z": None,
                "range_position": None,
            }

        latest_price = self.last_price()
        current_volume = self.last_volume()
        volume = self.volume_series()
        trailing = volume.tail(volume_window)
        average_volume = float(trailing.mean()) if not volume.empty else None
        std_volume = float(trailing.std(ddof=0)) if len(trailing) > 1 else None
        volume_z = None
        if std_volume and current_volume is not None and average_volume is not None:
            volume_z = (current_volume - average_volume) / std_volume

        high = float(self.history["high"].iloc[-1]) if "high" in self.history.columns else None
        low = float(self.history["low"].iloc[-1]) if "low" in self.history.columns else None
        range_position = 0.5
        if latest_price is not None and high is not None and low is not None and high != low:
            range_position = (latest_price - low) / (high - low)

        return {
            "latest_price": latest_price,
            "current_volume": current_volume,
            "average_volume": average_volume,
            "volume_z": volume_z,
            "range_position": range_position,
        }
