"""Rule-based classification of the macro backdrop, and the tones used to display it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

import pandas as pd

BPS_PER_PERCENT = 100.0


class Tone(Enum):
    """Directional colouring shared by macro badges and delta rows."""

    POSITIVE = ("positive", "↑", "rgba(78, 123, 82, 0.10)", "#4E7B52")
    NEGATIVE = ("negative", "↓", "rgba(165, 92, 69, 0.10)", "#A55C45")
    NEUTRAL = ("neutral", "→", "rgba(111, 123, 70, 0.10)", "#6F7B46")

    def __init__(self, name_: str, arrow: str, background: str, color: str) -> None:
        self.slug = name_
        self.arrow = arrow
        self.background = background
        self.color = color

    @classmethod
    def from_change(cls, value: float | None) -> Tone:
        """Tone a change by its sign, treating missing values as neutral."""
        if value is None or pd.isna(value):
            return cls.NEUTRAL
        if value > 0:
            return cls.POSITIVE
        return cls.NEGATIVE if value < 0 else cls.NEUTRAL

    @property
    def delta_class(self) -> str:
        return f"bb-macro-card-delta--{self.slug}"


@dataclass(frozen=True)
class Regime:
    """A regime call: its headline label and the sentence justifying it."""

    label: str
    body: str

    def __iter__(self):
        """Unpack as (label, body)."""
        return iter((self.label, self.body))


class MacroRegimes:
    """Classify duration, curve, inflation, and growth from the latest macro levels.

    Thresholds are expressed in basis points throughout, since the stored features are in
    percentage points and every rule here is about a move, not a level.
    """

    CURVE_INVERTED_BPS: ClassVar[float] = -25.0
    CURVE_STEEP_BPS: ClassVar[float] = 75.0
    CURVE_FLAT_BPS: ClassVar[float] = 35.0
    TWOS_TENS_INVERTED_BPS: ClassVar[float] = -10.0
    TWOS_TENS_FLAT_BPS: ClassVar[float] = 25.0
    TWOS_TENS_STEEP_BPS: ClassVar[float] = 25.0
    FIVES_THIRTIES_STEEP_BPS: ClassVar[float] = 35.0
    YIELD_MOVE_BPS: ClassVar[float] = 10.0
    UNEMPLOYMENT_MOVE_BPS: ClassVar[float] = 10.0
    INFLATION_HOT_PERCENT: ClassVar[float] = 3.0
    BREAKEVEN_REPRICING_BPS: ClassVar[float] = 25.0

    def __init__(self, latest: dict[str, float | None]) -> None:
        self.latest = latest

    @classmethod
    def from_matrix(cls, matrix: pd.DataFrame) -> MacroRegimes:
        """Build from the last non-null observation of each feature column."""
        return cls({column: _latest(matrix, column) for column in matrix.columns})

    def all(self) -> dict[str, Regime]:
        """Every regime call, keyed as the macro page renders them."""
        return {
            "duration_regime": self.duration,
            "curve_regime": self.curve,
            "inflation_regime": self.inflation,
            "growth_regime": self.growth,
        }

    @property
    def curve(self) -> Regime:
        """Classify curve shape from the visible front-to-long slope, falling back to 2s10s."""
        twos_tens = self._bps("UST_2S10S")
        fives_thirties = self._bps("UST_5S30S")
        full_curve = self._slope_bps("UST_3M_LEVEL", "UST_30Y_LEVEL")

        if full_curve is not None:
            if full_curve <= self.CURVE_INVERTED_BPS:
                return Regime(
                    "Curve Inverted", f"3M-to-30Y is inverted by {abs(full_curve):.0f} bps."
                )
            if full_curve >= self.CURVE_STEEP_BPS:
                return Regime("Curve Steep", f"3M-to-30Y slopes upward by {full_curve:.0f} bps.")
            if abs(full_curve) <= self.CURVE_FLAT_BPS and abs(twos_tens) <= self.TWOS_TENS_FLAT_BPS:
                return Regime("Curve Flat", "Front-to-long and 2s10s slopes are both compressed.")

        if twos_tens <= self.TWOS_TENS_INVERTED_BPS:
            return Regime("Curve Inverted", f"2s10s is inverted by {abs(twos_tens):.0f} bps.")
        if twos_tens >= self.TWOS_TENS_STEEP_BPS or fives_thirties >= self.FIVES_THIRTIES_STEEP_BPS:
            return Regime(
                "Curve Steep",
                f"2s10s is {twos_tens:.0f} bps and 5s30s is {fives_thirties:.0f} bps.",
            )
        return Regime("Curve Flat", "2s10s is near zero and the curve slope is compressed.")

    @property
    def duration(self) -> Regime:
        """Classify the duration backdrop from the 20-day move in 10Y yields."""
        move = self._bps("UST_10Y_CHANGE_20D")
        window = "over the last 20 trading days"
        if move <= -self.YIELD_MOVE_BPS:
            return Regime(
                "Duration Bullish", f"10Y yields have fallen {abs(move):.0f} bps {window}."
            )
        if move >= self.YIELD_MOVE_BPS:
            return Regime("Duration Bearish", f"10Y yields have risen {move:.0f} bps {window}.")
        return Regime(
            "Duration Neutral", f"10Y yields are range-bound, moving {move:+.0f} bps {window}."
        )

    @property
    def inflation(self) -> Regime:
        """Classify the inflation tone from CPI and the 20-day move in 5Y breakevens."""
        headline = self._value("CPI_YOY")
        short_run = self._value("CPI_3M_ANN")
        breakevens = self._bps("BEI_5Y_CHANGE_20D")

        if max(headline, short_run) > self.INFLATION_HOT_PERCENT:
            return Regime(
                "Inflation Hot",
                "Headline inflation or its short-term annualized pace remains above 3%.",
            )
        if breakevens >= self.BREAKEVEN_REPRICING_BPS:
            return Regime(
                "Inflation Repricing",
                f"5Y breakevens have risen {breakevens:.0f} bps over the last 20 trading days.",
            )
        return Regime(
            "Inflation Cooling", "CPI YoY is below 3% and 3M annualized inflation is contained."
        )

    @property
    def growth(self) -> Regime:
        """Classify the growth backdrop from the three-month change in unemployment."""
        move = self._bps("UNRATE_3M_CHANGE")
        window = "over the last three months"
        if move <= -self.UNEMPLOYMENT_MOVE_BPS:
            return Regime(
                "Growth Improving", f"Unemployment has fallen {abs(move):.0f} bps {window}."
            )
        if move >= self.UNEMPLOYMENT_MOVE_BPS:
            return Regime(
                "Growth Deteriorating", f"Unemployment has risen {move:.0f} bps {window}."
            )
        return Regime(
            "Growth Stable",
            f"Unemployment is broadly stable, moving {move:+.0f} bps over three months.",
        )

    def _value(self, feature_name: str, default: float = 0.0) -> float:
        """Return a feature level as a plain float, defaulting when it is unavailable."""
        value = self.latest.get(feature_name)
        return default if value is None or pd.isna(value) else float(value)

    def _bps(self, feature_name: str) -> float:
        """Return a feature stored in percentage points, restated in basis points."""
        return self._value(feature_name) * BPS_PER_PERCENT

    def _slope_bps(self, short_feature: str, long_feature: str) -> float | None:
        """Return long-minus-short slope in basis points, or None when either leg is missing."""
        short = self.latest.get(short_feature)
        long = self.latest.get(long_feature)
        if short is None or long is None or pd.isna(short) or pd.isna(long):
            return None
        return (float(long) - float(short)) * BPS_PER_PERCENT


@dataclass(frozen=True)
class StateCard:
    """One tile in the State of Macro grid: level, day-over-day change, and z-score badge."""

    label: str
    value: str
    delta: str
    delta_tone: Tone
    badge: str = ""
    badge_tone: Tone = Tone.NEUTRAL


def _latest(matrix: pd.DataFrame, feature_name: str) -> float | None:
    if feature_name not in matrix.columns:
        return None
    series = matrix[feature_name].dropna()
    return None if series.empty else float(series.iloc[-1])
