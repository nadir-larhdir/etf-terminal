"""View models for the per-security panel: the price card and the metadata list."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from dashboard.format import Formatter
from fixed_income.series import volume_multiple

FMT = Formatter(missing="N/A")


@dataclass(frozen=True)
class PriceCard:
    """Last price with its day-over-day change, already formatted for display."""

    ticker: str
    price: str
    change: str
    change_percent: str
    change_class: str

    @classmethod
    def from_history(cls, ticker: str, history: pd.DataFrame) -> PriceCard | None:
        """Build the card, or None when there is no close to show."""
        closes = history["close"].dropna() if "close" in history.columns else pd.Series(dtype=float)
        if closes.empty:
            return None

        last = float(closes.iloc[-1])
        previous = float(closes.iloc[-2]) if len(closes) > 1 else last
        change = last - previous
        percent = (change / previous * 100.0) if previous != 0 else 0.0
        return cls(
            ticker=ticker,
            price=FMT.number(last),
            change=FMT.number(change, signed=True),
            change_percent=FMT.percent(percent, signed=True),
            change_class="db-price-pos" if change >= 0 else "db-price-neg",
        )


def metadata_rows(metadata: dict[str, object], history: pd.DataFrame) -> list[tuple[str, str]]:
    """Return the label/value pairs shown under the price card."""

    def text(key: str) -> str:
        value = metadata.get(key)
        return str(value) if value else FMT.missing

    return [
        ("Category", text("category")),
        ("Benchmark", text("benchmark_index")),
        ("Duration", text("duration_bucket")),
        ("Issuer", text("issuer")),
        ("YTM", FMT.percent(metadata.get("yield_to_maturity"))),
        ("Liquidity", FMT.multiple(volume_multiple(history))),
        ("AUM", FMT.compact(metadata.get("total_assets"))),
        ("Exp Ratio", FMT.percent(metadata.get("expense_ratio"))),
    ]
