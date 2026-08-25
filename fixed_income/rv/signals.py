"""The single z-score -> relative-value signal mapping used across RV analytics and UI."""

from __future__ import annotations

from enum import Enum

RICH_THRESHOLD = 1.0
EXTREME_THRESHOLD = 2.0


class SignalRegime(Enum):
    """Where a pair spread sits versus its own distribution, and what that implies."""

    CHEAP_EXTREME = ("CHEAP / EXTREME", "-2σ", -EXTREME_THRESHOLD)
    CHEAP = ("CHEAP", "-1σ", -RICH_THRESHOLD)
    NEUTRAL = ("NEUTRAL", "", 0.0)
    RICH = ("RICH", "+1σ", RICH_THRESHOLD)
    RICH_EXTREME = ("RICH / EXTREME", "+2σ", EXTREME_THRESHOLD)

    def __init__(self, label: str, threshold: str, bound: float) -> None:
        self.label = label
        self.threshold = threshold
        self.bound = bound

    @classmethod
    def from_zscore(cls, zscore: float) -> SignalRegime:
        """Classify a z-score, treating NaN as neutral."""
        if zscore != zscore:  # NaN
            return cls.NEUTRAL
        if zscore >= EXTREME_THRESHOLD:
            return cls.RICH_EXTREME
        if zscore >= RICH_THRESHOLD:
            return cls.RICH
        if zscore <= -EXTREME_THRESHOLD:
            return cls.CHEAP_EXTREME
        if zscore <= -RICH_THRESHOLD:
            return cls.CHEAP
        return cls.NEUTRAL

    @property
    def is_extreme(self) -> bool:
        return self in (self.RICH_EXTREME, self.CHEAP_EXTREME)

    @property
    def is_dislocated(self) -> bool:
        """True once the spread has breached +/-1 sigma in either direction."""
        return self is not SignalRegime.NEUTRAL

    @property
    def compact_label(self) -> str:
        """RICH / CHEAP / NEUTRAL without the extremity qualifier, for KPI strips."""
        return self.label.split(" / ")[0]

    @property
    def action(self) -> str:
        """Screener action for the pair: WATCH once dislocated, otherwise HOLD."""
        return "WATCH" if self.is_dislocated else "HOLD"

    def trade_bias(self, left_ticker: str, right_ticker: str) -> str:
        """Describe the directional trade the dislocation implies for this pair."""
        if self is SignalRegime.RICH_EXTREME:
            return f"Fade rich: Short {left_ticker} / Long {right_ticker}"
        if self is SignalRegime.RICH:
            return f"Monitor richening in {left_ticker} vs {right_ticker}"
        if self is SignalRegime.CHEAP_EXTREME:
            return f"Fade cheap: Long {left_ticker} / Short {right_ticker}"
        if self is SignalRegime.CHEAP:
            return f"Monitor cheapening in {left_ticker} vs {right_ticker}"
        return "No strong RV dislocation signal"
