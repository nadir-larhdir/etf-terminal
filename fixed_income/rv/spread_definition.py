from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpreadDefinition:
    left_ticker: str
    right_ticker: str

    @property
    def name(self) -> str:
        return f"{self.left_ticker}/{self.right_ticker}"


@dataclass(frozen=True)
class RVAnalyticsSnapshot:
    name: str
    zscore: float
    correlation_20d: float
    stability: float
