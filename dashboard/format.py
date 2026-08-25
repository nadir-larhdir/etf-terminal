"""One display-formatting vocabulary for the whole dashboard.

Every formatter coerces its input first and renders `missing` for anything that is not a
finite number, so call sites never repeat a None/NaN guard. Surfaces differ only in the
placeholder they want ("-", "N/A", "n/a"), which is the sole knob on `Formatter`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

BPS_PER_PERCENT = 100.0
PER_MILLION = 10_000.0
_MAGNITUDES = ((1_000_000_000.0, "B"), (1_000_000.0, "M"), (1_000.0, "K"))


def to_number(value: object) -> float | None:
    """Coerce anything to a finite float, or None when it cannot represent a quantity."""
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


@dataclass(frozen=True)
class Formatter:
    """Renders numbers in the units a fixed-income desk expects."""

    missing: str = "-"

    def number(self, value: object, decimals: int = 2, *, signed: bool = False) -> str:
        """Comma-separated fixed-point number, optionally sign-forced."""
        return self._render(value, f"{'+' if signed else ''},.{decimals}f")

    def percent(self, value: object, decimals: int = 2, *, signed: bool = False) -> str:
        """A value already expressed in percentage points: 4.37 -> '4.37%'."""
        return self._render(value, f"{'+' if signed else ''},.{decimals}f", suffix="%")

    def proportion(self, value: object, decimals: int = 0) -> str:
        """A 0-1 proportion rendered as a percentage: 0.85 -> '85%'."""
        return self._render(value, f".{decimals}%")

    def bps(self, value: object, decimals: int = 0, *, signed: bool = False) -> str:
        """A value already expressed in basis points: 412 -> '412 bps'."""
        return self._render(value, f"{'+' if signed else ''},.{decimals}f", suffix=" bps")

    def percent_as_bps(self, value: object, decimals: int = 0, *, signed: bool = False) -> str:
        """A value stored in percentage points, shown in basis points: 4.12 -> '412 bps'."""
        return self.bps(_scale(value, BPS_PER_PERCENT), decimals, signed=signed)

    def years(self, value: object, decimals: int = 1) -> str:
        """A duration in years: 5.24 -> '5.2y'."""
        return self._render(value, f".{decimals}f", suffix="y")

    def multiple(self, value: object, decimals: int = 2) -> str:
        """A ratio against a baseline: 1.234 -> 'x1.23'."""
        return self._render(value, f".{decimals}f", prefix="x")

    def money(self, value: object, decimals: int = 0) -> str:
        """An absolute dollar amount: 12345 -> '$12,345'."""
        return self._render(value, f",.{decimals}f", prefix="$")

    def money_per_million(self, value: object, decimals: int = 0) -> str:
        """A per-share dollar risk restated per $1MM notional."""
        return self.money(_scale(value, PER_MILLION), decimals)

    def decimal_as_bps(self, value: object, decimals: int = 1, *, signed: bool = True) -> str:
        """A per-unit sensitivity stored as a decimal, shown in basis points."""
        return self.bps(_scale(value, PER_MILLION), decimals, signed=signed)

    def zscore(self, value: object, decimals: int = 2) -> str:
        """A standard-deviation score: 1.234 -> 'z +1.23'."""
        return self._render(value, f"+.{decimals}f", prefix="z ")

    def compact(self, value: object, decimals: int = 1) -> str:
        """Large magnitudes in K/M/B: 1_200_000_000 -> '1.2B'. B=billion, M=million, K=thousand."""
        numeric = to_number(value)
        if numeric is None:
            return self.missing
        magnitude = abs(numeric)
        for threshold, suffix in _MAGNITUDES:
            if magnitude >= threshold:
                return f"{numeric / threshold:.{decimals}f}{suffix}"
        return f"{numeric:,.0f}"

    def _render(self, value: object, spec: str, *, prefix: str = "", suffix: str = "") -> str:
        numeric = to_number(value)
        if numeric is None:
            return self.missing
        return f"{prefix}{numeric:{spec}}{suffix}"


class MacroUnit(Enum):
    """The quoting convention for a macro feature, applied identically on every page."""

    BPS = "bps"
    PERCENT = "percent"
    ZSCORE = "zscore"
    PLAIN = "plain"

    def level(self, value: object, formatter: Formatter) -> str:
        """Render a level in this feature's natural unit."""
        if self is MacroUnit.BPS:
            return formatter.percent_as_bps(value)
        if self is MacroUnit.PERCENT:
            return formatter.percent(value)
        if self is MacroUnit.ZSCORE:
            return formatter.zscore(value)
        return formatter.number(value)

    def delta(self, value: object, formatter: Formatter) -> str:
        """Render a change in this feature, always signed.

        Rate and spread moves are quoted in basis points regardless of how the level
        reads, which is how a desk discusses a day-over-day move.
        """
        if self in (MacroUnit.BPS, MacroUnit.PERCENT):
            return formatter.percent_as_bps(value, 1, signed=True)
        if self is MacroUnit.ZSCORE:
            return formatter.zscore(value)
        return formatter.number(value, signed=True)


_PERCENT_STEMS = ("UST_", "BEI_", "CPI_", "FEDFUNDS", "UNRATE", "REAL_RATE")
_CURVE_STEMS = ("UST_2S10S", "UST_5S30S", "UST_3M10Y")


def macro_unit(feature_name: str) -> MacroUnit:
    """Resolve a macro feature's quoting convention from its name.

    Rule-based rather than an explicit table so a newly derived feature inherits the
    convention of the series it is built from instead of silently falling back to plain.
    """
    if feature_name.endswith(("_Z20", "_Z60")):
        return MacroUnit.ZSCORE
    if "OAS" in feature_name or feature_name.startswith(_CURVE_STEMS):
        return MacroUnit.BPS
    if feature_name.startswith(_PERCENT_STEMS):
        return MacroUnit.PERCENT
    return MacroUnit.PLAIN


def _scale(value: object, factor: float) -> float | None:
    numeric = to_number(value)
    return None if numeric is None else numeric * factor
