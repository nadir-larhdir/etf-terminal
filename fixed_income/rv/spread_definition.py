"""Data models for defining and summarising relative-value pair trades."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpreadDefinition:
    """Identifies a relative-value pair as an ordered (left, right) ticker pair."""

    left_ticker: str
    right_ticker: str

    @property
    def name(self) -> str:
        """Return a slash-separated display name for the pair."""
        return f"{self.left_ticker}/{self.right_ticker}"


@dataclass(frozen=True)
class RVAnalyticsSnapshot:
    """Point-in-time summary of key RV metrics for a spread pair."""

    name: str
    zscore: float
    correlation_20d: float
    stability: float
