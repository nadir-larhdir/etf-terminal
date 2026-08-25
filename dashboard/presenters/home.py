"""View models for the homepage, built from the price and macro-feature stores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import pandas as pd

from config import normalize_asset_class
from dashboard.format import Formatter, macro_unit
from fixed_income.analytics.result_models import RegimeSnapshot
from fixed_income.series import as_text

FMT = Formatter(missing="n/a")

# Trailing price history per ticker, as returned by the store.
Histories = dict[str, pd.DataFrame]

MAX_SNAPSHOT_TILES = 7
MAX_VOLUME_LEADERS = 4
MAX_EXAMPLE_TICKERS = 4
VOLUME_BASELINE_DAYS = 30

# Every figure on the page comes from this many trailing sessions, fetched once.
RECENT_SESSIONS = VOLUME_BASELINE_DAYS
# The macro strip shows a level and its change, so it needs two observations per feature.
SNAPSHOT_OBSERVATIONS = 2


@dataclass(frozen=True)
class SnapshotTile:
    """One macro reading in the top strip: its level, its move, and the move's direction."""

    label: str
    sublabel: str
    value: str
    delta: str
    delta_class: str
    indicator: str

    @classmethod
    def from_move(cls, feature_name: str, label: str, sublabel: str, latest: float, delta: float):
        unit = macro_unit(feature_name)
        direction = 0 if delta == 0 else (1 if delta > 0 else -1)
        return cls(
            label=label,
            sublabel=sublabel,
            value=unit.level(latest, FMT),
            delta=unit.delta(delta, FMT),
            delta_class={1: "home-delta-up", -1: "home-delta-down", 0: "home-delta-flat"}[
                direction
            ],
            indicator={1: "▲", -1: "▼", 0: "•"}[direction],
        )


@dataclass(frozen=True)
class RegimeCard:
    """The regime gauge: its label, the accent colour and copy that go with it, and the marker."""

    label: str
    accent: str
    body: str
    position: float

    COPY: ClassVar[dict[str, tuple[str, str]]] = {
        "Risk Off": (
            "#FF5A36",
            "Liquidity is tightening and credit is leaning defensive across the "
            "fixed-income complex.",
        ),
        "Neutral": (
            "#FFD166",
            "Signals are mixed. Keep the focus on relative value and execution quality "
            "rather than a broad macro chase.",
        ),
        "Risk On": (
            "#00C176",
            "Rates and spread conditions are leaning constructive, with a more supportive "
            "tone for carry.",
        ),
    }
    FALLBACK: ClassVar[tuple[str, str]] = COPY["Neutral"]

    @classmethod
    def from_snapshot(cls, snapshot: RegimeSnapshot) -> RegimeCard:
        accent, body = cls.COPY.get(snapshot.label, cls.FALLBACK)
        return cls(label=snapshot.label, accent=accent, body=body, position=snapshot.position)


@dataclass(frozen=True)
class StatCard:
    """One headline counter in the stat row."""

    icon: str
    label: str
    value: str
    note: str
    is_date: bool = False


@dataclass(frozen=True)
class PulseRow:
    """One line in the Market Pulse card."""

    title: str
    body: str
    tag: str
    tag_class: str


@dataclass(frozen=True)
class ContextCard:
    """One explanatory card, optionally offering a link to another view."""

    kicker: str
    title: str
    body: str
    cta_label: str = ""
    cta_view: str = ""


@dataclass(frozen=True)
class DirectionBadge:
    """Net up-minus-down count for an asset class, with the word that describes it."""

    net: int
    label: str

    @classmethod
    def from_net(cls, net: int) -> DirectionBadge:
        if net > 0:
            return cls(net, "Broad" if net >= 2 else "Firm")
        if net < 0:
            return cls(net, "Weakening" if net <= -2 else "Soft")
        return cls(0, "Stable")


class HomePresenter:
    """Builds every view model the homepage needs from the stores it is given."""

    SNAPSHOT_FEATURES: ClassVar[dict[str, tuple[str, str]]] = {
        "UST_10Y_LEVEL": ("US 10Y", "UST"),
        "UST_2Y_LEVEL": ("US 2Y", "UST"),
        "HY_OAS_LEVEL": ("HY OAS", "Spread"),
        "IG_OAS_LEVEL": ("IG OAS", "Spread"),
        "UST_2S10S": ("2s10s", "Curve"),
        "BEI_5Y": ("5Y BEI", "Inflation"),
        "FEDFUNDS_LEVEL": ("Fed Funds", "Policy"),
    }

    PULSE_ROWS: ClassVar[tuple[PulseRow, ...]] = (
        PulseRow("Rates", "Belly leadership", "WATCH", "elevated"),
        PulseRow("Credit", "IG vs HY beta", "CONFIRM", "mixed"),
        PulseRow("Liquidity", "Volume vs 30D", "NORMAL", "active"),
        PulseRow("Flows", "Defensive bias", "ELEVATED", "neutral"),
    )

    NO_HISTORY_LABEL = "Awaiting history sync"

    def latest_market_date(self, histories: Histories) -> str:
        """Return the most recent priced date across the universe, or a placeholder."""
        dates = [frame.index.max() for frame in histories.values() if not frame.empty]
        return max(dates).date().isoformat() if dates else self.NO_HISTORY_LABEL

    def snapshot_tiles(self, matrix: pd.DataFrame) -> list[SnapshotTile]:
        """Build the top macro strip, skipping features with no stored history."""
        if matrix.empty:
            return []

        tiles = []
        for feature_name, (label, sublabel) in self.SNAPSHOT_FEATURES.items():
            if feature_name not in matrix.columns:
                continue
            series = matrix[feature_name].dropna()
            if series.empty:
                continue
            latest = float(series.iloc[-1])
            previous = float(series.iloc[-2]) if len(series) > 1 else latest
            tiles.append(
                SnapshotTile.from_move(feature_name, label, sublabel, latest, latest - previous)
            )
        return tiles[:MAX_SNAPSHOT_TILES]

    def volume_leaders(self, histories: Histories) -> list[str]:
        """Return the most actively traded tickers versus their own recent average."""
        ranking = []
        for ticker, history in histories.items():
            if history.empty or "volume" not in history.columns:
                continue
            volume = history["volume"].dropna()
            if volume.empty:
                continue
            baseline = float(volume.tail(VOLUME_BASELINE_DAYS).mean())
            latest = float(volume.iloc[-1])
            ranking.append((ticker, 0.0 if baseline == 0 else latest / baseline))

        ranking.sort(key=lambda item: item[1], reverse=True)
        return [
            f"{ticker} ({FMT.multiple(ratio)})" for ticker, ratio in ranking[:MAX_VOLUME_LEADERS]
        ]

    def pulse_rows(self, volume_leaders: list[str]) -> list[PulseRow]:
        """The Market Pulse lines, with the most-active names as a row of the same shape."""
        rows = list(self.PULSE_ROWS)
        if volume_leaders:
            rows.append(
                PulseRow(
                    "Most Active",
                    ", ".join(volume_leaders),
                    f"TOP {len(volume_leaders)}",
                    "active",
                )
            )
        return rows

    def context_cards(self) -> list[ContextCard]:
        """The three explanatory cards under the stat row."""
        return [
            ContextCard(
                kicker="Project Overview",
                title="Fixed income ETF decision support",
                body=(
                    "Price action, liquidity, and relative value in one place. Market framing "
                    "first, then security-level analysis and RV follow-through."
                ),
            ),
            ContextCard(
                kicker="Morning Setup",
                title="What to answer before the open",
                body=(
                    "Where is duration leading? Is credit defensive or constructive? Which ETFs "
                    "show unusual participation? Where are the cleanest dislocations?"
                ),
            ),
            ContextCard(
                kicker="News Layer",
                title="Curated fixed income headlines",
                body=(
                    "Rates, credit, ETF flow, and macro events, filtered for relevance and "
                    "ordered newest first."
                ),
                cta_label="View latest news →",
                cta_view="News",
            ),
        ]

    def stat_cards(
        self, *, active_etfs: int, bucket_count: int, latest_date: str
    ) -> list[StatCard]:
        """Build the three headline counters."""
        return [
            StatCard("active", "Active ETFs", str(active_etfs), "+2 vs last week"),
            StatCard("bucket", "Universe Buckets", str(bucket_count), "Stable grouping mix"),
            StatCard(
                "calendar",
                "Latest Market Date",
                latest_date,
                "Refreshed and aligned",
                is_date=True,
            ),
        ]

    def bucket_summary(self, securities: pd.DataFrame, histories: Histories) -> pd.DataFrame:
        """Group the universe by asset class with counts, examples, and net 1-day direction."""
        columns = ["ASSET CLASS", "ETF COUNT", "EXAMPLE TICKERS", "VS 1D"]
        if securities.empty:
            return pd.DataFrame(columns=columns)

        frame = securities.copy()
        frame["asset_class"] = (
            as_text(frame["asset_class"].fillna("Other")).str.strip().map(normalize_asset_class)
        )
        directions = self._daily_directions(histories)

        grouped = (
            frame.groupby("asset_class", dropna=False)["ticker"]
            .agg(
                ETF_COUNT="count",
                EXAMPLE_TICKERS=lambda values: ", ".join(list(values)[:MAX_EXAMPLE_TICKERS]),
                VS_1D=lambda values: sum(directions.get(str(value), 0) for value in values),
            )
            .reset_index()
            .sort_values(["ETF_COUNT", "asset_class"], ascending=[False, True])
            .reset_index(drop=True)
        )
        return grouped.rename(
            columns={
                "asset_class": "ASSET CLASS",
                "ETF_COUNT": "ETF COUNT",
                "EXAMPLE_TICKERS": "EXAMPLE TICKERS",
                "VS_1D": "VS 1D",
            }
        )[columns]

    def _daily_directions(self, histories: Histories) -> dict[str, int]:
        """Map each ticker to +1 up, -1 down, or 0 flat on its most recent close."""
        directions = {}
        for ticker, history in histories.items():
            closes = history["close"].dropna() if "close" in history.columns else pd.Series()
            if len(closes) < 2:
                directions[ticker] = 0
                continue
            last, previous = float(closes.iloc[-1]), float(closes.iloc[-2])
            directions[ticker] = (last > previous) - (last < previous)
        return directions


def universe_tickers(securities: pd.DataFrame) -> list[str]:
    """Return the ticker column as plain strings, tolerating an empty universe."""
    if securities.empty or "ticker" not in securities.columns:
        return []
    return as_text(securities["ticker"]).tolist()
