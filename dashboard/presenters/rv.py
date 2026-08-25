"""View models for the RV tab: metric cards, screener badges, and diagnostic labels."""

from __future__ import annotations

from dataclasses import dataclass

from dashboard.format import Formatter
from fixed_income.rv.signals import SignalRegime

FMT = Formatter(missing="--")

INK = "var(--etf-ink)"
UP = "var(--etf-up)"
DOWN = "var(--etf-down)"
REGIME_ACCENT = "#C4882A"


@dataclass(frozen=True)
class MetricCard:
    """One RV metric card: headline value plus a labelled sub-reading."""

    label: str
    value: str
    sub_label: str = ""
    sub_value: str = ""
    color: str = INK


@dataclass(frozen=True)
class PillBadge:
    """The screener's WATCH / HOLD pill, with the colours it is drawn in."""

    label: str
    color: str
    border: str
    background: str

    STYLES = {
        "WATCH": ("#C4882A", "rgba(196,136,42,0.45)", "rgba(196,136,42,0.06)"),
        "HOLD": ("#6B6560", "rgba(141,135,121,0.40)", "rgba(141,135,121,0.05)"),
    }

    @classmethod
    def from_label(cls, label: str) -> PillBadge:
        color, border, background = cls.STYLES.get(label, cls.STYLES["HOLD"])
        return cls(label=label, color=color, border=border, background=background)


class RVPresenter:
    """Builds the RV tab's headline cards and diagnostic labels."""

    def signal_color(self, regime: SignalRegime) -> str:
        """Rich reads as a short, cheap as a long, neutral as plain ink."""
        if regime is SignalRegime.RICH or regime is SignalRegime.RICH_EXTREME:
            return DOWN
        if regime is SignalRegime.CHEAP or regime is SignalRegime.CHEAP_EXTREME:
            return UP
        return INK

    def top_cards(
        self,
        *,
        zscore: float,
        stability: float,
        deviation_percent: float,
        fair_value_percent: float,
        forward_return_percent: float,
        hit_rate: float,
        event_count: int,
    ) -> list[MetricCard]:
        """The four headline cards above the RV charts."""
        regime = SignalRegime.from_zscore(zscore)
        hits = int(round(hit_rate * event_count))
        return [
            MetricCard(
                "RV Signal",
                regime.compact_label,
                "Z-Score",
                FMT.number(zscore),
                self.signal_color(regime),
            ),
            MetricCard(
                "Regime",
                regime.compact_label,
                "Stability",
                f"{FMT.number(stability, 0)} / 100",
                REGIME_ACCENT,
            ),
            MetricCard(
                "Dislocation",
                FMT.percent(deviation_percent, signed=True),
                "Fair Value (20D)",
                FMT.percent(fair_value_percent, signed=True),
                DOWN if deviation_percent >= 0 else UP,
            ),
            MetricCard(
                "Fwd Return (20D)",
                FMT.percent(forward_return_percent, signed=True),
                "Hit Rate",
                f"{FMT.proportion(hit_rate)} ({hits}/{event_count})",
                UP if forward_return_percent >= 0 else DOWN,
            ),
        ]

    def adf_label(self, pvalue: float | None, is_stationary: bool | None) -> str:
        """Report the ADF p-value alongside whether it implies mean reversion."""
        if pvalue is None or is_stationary is None:
            return FMT.missing
        return f"{pvalue:.4f} ({'MR' if is_stationary else 'No MR'})"
