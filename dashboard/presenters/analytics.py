"""View models for the Analytics tab: metric cards, risk colouring, and the read panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from dashboard.format import Formatter
from fixed_income.analytics import format_oas_proxy_label
from fixed_income.series import volume_multiple

FMT = Formatter()

INK = "#1F271C"
GOOD = "#6FAF72"
WARN = "#D4A017"
ALERT = "#C97C6B"

NEUTRAL_ACCENT = "#8D8779"
RATE_ACCENT = "#5DA9E9"
SPREAD_ACCENT = "#8AA05A"

PER_MILLION = 10_000.0
DURATION_SCALE_MAX_YEARS = 30.0
DV01_LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class RiskScale:
    """Maps a magnitude to a traffic-light colour using two thresholds.

    One scale replaces the per-metric colour functions: they differed only in their
    thresholds, in whether the raw value is restated per $1MM, and in whether a larger
    number is worse (risk) or better (model fit).
    """

    good_below: float
    warn_below: float
    factor: float = 1.0
    higher_is_worse: bool = True

    def color(self, value: float | None) -> str:
        """Return the colour for a value, or the neutral ink when it is unavailable."""
        if value is None:
            return INK
        magnitude = abs(value) * self.factor
        if not self.higher_is_worse:
            return (
                GOOD
                if magnitude >= self.warn_below
                else (WARN if magnitude >= self.good_below else ALERT)
            )
        if magnitude <= self.good_below:
            return GOOD
        return WARN if magnitude <= self.warn_below else ALERT


DURATION_YEARS = RiskScale(good_below=3.0, warn_below=7.0)
DV01_PER_MILLION = RiskScale(good_below=150.0, warn_below=500.0, factor=PER_MILLION)
CS_BETA_BPS = RiskScale(good_below=1.0, warn_below=3.0, factor=PER_MILLION)
CS01_PER_MILLION = RiskScale(good_below=100.0, warn_below=400.0, factor=PER_MILLION)
MODEL_FIT = RiskScale(good_below=0.25, warn_below=0.6, higher_is_worse=False)


@dataclass(frozen=True)
class MetricCard:
    """One large-value card: its label, formatted value, colour, and optional footer."""

    label: str
    value: str
    color: str = INK
    accent: str = NEUTRAL_ACCENT
    footer: str | None = None
    show_bottom_border: bool = True


@dataclass(frozen=True)
class Gauge:
    """A 0-100 fill used to show model fit."""

    percent: float

    @classmethod
    def from_fraction(cls, value: float | None) -> Gauge | None:
        if value is None:
            return None
        return cls(percent=max(0.0, min(value, 1.0)) * 100.0)


@dataclass(frozen=True)
class DurationScale:
    """Marker position for a duration on a fixed 0-30Y axis."""

    percent: float
    max_years: float = DURATION_SCALE_MAX_YEARS

    @classmethod
    def from_years(cls, duration: float | None) -> DurationScale | None:
        if duration is None:
            return None
        return cls(percent=max(0.0, min(duration / DURATION_SCALE_MAX_YEARS, 1.0)) * 100.0)


class AnalyticsPresenter:
    """Builds the Analytics tab's cards and narrative copy from an ETF and its snapshot."""

    LIQUIDITY_HIGH_Z: ClassVar[float] = 2.0
    LIQUIDITY_QUIET_Z: ClassVar[float] = -1.0

    def instrument_cards(self, etf: Any) -> list[MetricCard]:
        """The provider-reported characteristics row."""
        years_to_maturity = etf.metadata_number("years_to_maturity")
        return [
            MetricCard("YTM (SEC)", FMT.percent(etf.metadata_number("yield_to_maturity"))),
            MetricCard("OAS", FMT.bps(etf.metadata_number("oas"))),
            MetricCard(
                "Years to Maturity",
                FMT.years(years_to_maturity),
                DURATION_YEARS.color(years_to_maturity),
            ),
            MetricCard("Convexity", FMT.number(etf.metadata_number("convexity"))),
        ]

    def rate_risk_cards(
        self,
        analytics: Any,
        *,
        duration_method: str,
        duration_source: str,
        dv01_footer: str | None = None,
        duration_footer: str | None = None,
    ) -> list[MetricCard]:
        """The modelled rate-risk row."""
        return [
            MetricCard(
                "Est. Duration",
                FMT.years(analytics.estimated_duration),
                DURATION_YEARS.color(analytics.estimated_duration),
                RATE_ACCENT,
                footer=duration_footer,
            ),
            MetricCard(
                "DV01 / $1MM",
                FMT.money_per_million(analytics.dv01_per_share),
                DV01_PER_MILLION.color(analytics.dv01_per_share),
                RATE_ACCENT,
                footer=dv01_footer,
            ),
            MetricCard("Duration Method", duration_method),
            MetricCard("Duration Source", duration_source),
        ]

    def spread_risk_cards(self, analytics: Any) -> list[MetricCard]:
        """The credit-spread row, empty when the ETF has no spread proxy."""
        if not self.has_spread_risk(analytics):
            return []
        return [
            MetricCard(
                "OAS Proxy Used",
                format_oas_proxy_label(analytics.spread_proxy_used),
                accent=SPREAD_ACCENT,
            ),
            MetricCard(
                "CS Beta",
                FMT.decimal_as_bps(analytics.spread_beta_per_bp),
                CS_BETA_BPS.color(analytics.spread_beta_per_bp),
                SPREAD_ACCENT,
            ),
            MetricCard(
                "Proxy CS01 / $1MM",
                FMT.money_per_million(analytics.spread_dv01_proxy_per_share),
                CS01_PER_MILLION.color(analytics.spread_dv01_proxy_per_share),
                SPREAD_ACCENT,
            ),
            MetricCard(
                "Credit Spread R²",
                FMT.number(analytics.spread_model_r2),
                MODEL_FIT.color(analytics.spread_model_r2),
                SPREAD_ACCENT,
                show_bottom_border=False,
            ),
        ]

    @staticmethod
    def has_spread_risk(analytics: Any) -> bool:
        """True when the ETF has both a spread proxy and a fitted beta."""
        return analytics.spread_proxy_used is not None and analytics.spread_beta_per_bp is not None

    def liquidity_regime(self, volume_z: float | None) -> str:
        """Classify today's participation against the ETF's own recent range."""
        if volume_z is None:
            return "NORMAL"
        if volume_z > self.LIQUIDITY_HIGH_Z:
            return "HIGH ACTIVITY"
        return "QUIET" if volume_z < self.LIQUIDITY_QUIET_Z else "NORMAL"

    def liquidity_summary(self, etf: Any) -> str:
        """One line describing volume against its 30-day average."""
        return (
            f"Current volume is running at {FMT.multiple(volume_multiple(etf.history))} "
            "the 30-day average."
        )

    def dv01_change_footer(self, etf: Any, duration: float | None) -> str | None:
        """Percentage change in DV01 over the last 30 sessions, or None without the history."""
        if duration is None or etf.history.empty or "adj_close" not in etf.history.columns:
            return None
        prices = etf.history["adj_close"].astype(float).dropna()
        if len(prices) < DV01_LOOKBACK_DAYS + 1:
            return None
        prior = float(prices.iloc[-(DV01_LOOKBACK_DAYS + 1)])
        if prior == 0:
            return None
        percent = ((float(prices.iloc[-1]) / prior) - 1.0) * 100.0
        arrow = "↑" if percent > 0 else "↓" if percent < 0 else "→"
        return f"30d {arrow} {abs(percent):.1f}%"

    def read_headline(self, etf: Any) -> str:
        """Headline for the Current Read panel: duration bucket plus category."""
        metadata = etf.metadata or {}
        category = str(metadata.get("category") or etf.asset_class or "Fixed Income")
        bucket = str(metadata.get("duration_bucket") or "").strip()
        return f"{bucket} {category}" if bucket and bucket.upper() != "N/A" else category

    def read_body(
        self, etf: Any, analytics: Any, *, duration_method: str, duration_source: str
    ) -> str:
        """Body copy for the Current Read panel."""
        benchmark = str((etf.metadata or {}).get("benchmark_index") or FMT.missing)
        return (
            f"Benchmark: {benchmark}. Duration is {FMT.years(analytics.estimated_duration)} "
            f"and DV01 is {FMT.money_per_million(analytics.dv01_per_share)} per $1MM "
            f"from {duration_method.lower()} ({duration_source})."
        )

    def oas_move_explanation(self, analytics: Any) -> str:
        """Plain-English price impact of a one basis point spread widening."""
        if not self.has_spread_risk(analytics):
            return "OAS 1 bp move interpretation unavailable."
        impact = analytics.spread_beta_per_bp * PER_MILLION
        return f"+1bp OAS widening -> {FMT.bps(impact, 2, signed=True)} price change."
