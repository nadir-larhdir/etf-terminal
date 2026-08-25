"""Homepage: market snapshot strip, hero, regime card, stat cards, and universe table.

All figures come from `HomePresenter` and all markup from `dashboard/templates/home`;
this module only decides the Streamlit layout.
"""

from __future__ import annotations

import base64
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

from dashboard.cache import (
    app_cache_key,
    cached_recent_feature_matrix,
    cached_recent_price_history,
)
from dashboard.components import DashboardTable
from dashboard.navigation import nav_button
from dashboard.perf import timed_block
from dashboard.presenters import DirectionBadge, HomePresenter, RegimeCard
from dashboard.presenters.home import (
    RECENT_SESSIONS,
    SNAPSHOT_OBSERVATIONS,
    universe_tickers,
)
from dashboard.render import render
from stores.protocols import MacroFeatureReader, PriceHistoryReader

HERO_IMAGE_PATH = Path(__file__).resolve().parents[1] / "assets" / "home_hero.png"

# The page is one content column and one rail. Everything on the left lines up with the
# hero and everything on the right with the regime card, because they are the same columns.
CONTENT_SPLIT = (2.3, 1.0)


class HomePage:
    """Render the homepage and its market framing layer."""

    def __init__(
        self,
        price_store: PriceHistoryReader,
        macro_feature_store: MacroFeatureReader,
        regime_analytics,
    ) -> None:
        self.price_store = price_store
        self.macro_feature_store = macro_feature_store
        self.presenter = HomePresenter()
        self.regime_analytics = regime_analytics
        self.table = DashboardTable()

    def render(self, securities: pd.DataFrame) -> None:
        """Render the full homepage."""
        # One windowed query serves the market date, the volume leaders and the daily
        # direction column; a second serves the macro strip. Both are cached, so a rerun
        # from switching view does no database work at all.
        cache_key = app_cache_key(self.price_store.engine)
        with timed_block("home.recent_history"):
            histories = cached_recent_price_history(
                cache_key,
                tuple(universe_tickers(securities)),
                RECENT_SESSIONS,
                self.price_store,
            )
        with timed_block("home.market_snapshot"):
            tiles = self.presenter.snapshot_tiles(
                cached_recent_feature_matrix(
                    cache_key,
                    tuple(HomePresenter.SNAPSHOT_FEATURES),
                    SNAPSHOT_OBSERVATIONS,
                    self.macro_feature_store,
                )
            )

        latest_date = self.presenter.latest_market_date(histories)
        bucket_summary = self._bucket_summary_table(securities, histories)
        volume_leaders = self.presenter.volume_leaders(histories)
        with timed_block("home.regime"):
            regime = RegimeCard.from_snapshot(self.regime_analytics.current_regime())

        stat_cards = self.presenter.stat_cards(
            active_etfs=len(securities),
            bucket_count=len(bucket_summary.index),
            latest_date=latest_date,
        )

        _markdown(render("home/market_strip.html", tiles=tiles, latest_date=latest_date))

        # One two-column layout for the whole page rather than a row per band: the rail
        # then flows directly under the regime card, and the columns cannot drift apart.
        content_col, rail_col = st.columns(CONTENT_SPLIT, vertical_alignment="top")
        # Both columns are keyed so one stylesheet rule owns their vertical rhythm; the
        # blocks inside carry no margins, so every gap on the page is that one value.
        with content_col, st.container(key="home_content"):
            _markdown(render("home/hero.html", hero_src=_hero_image_src()))
            _markdown(render("home/stat_cards.html", cards=stat_cards))
            self._render_context_cards()
            _markdown('<div class="home-section-title">Universe Snapshot</div>')
            self.table.render(bucket_summary, hide_index=True, height=270)
        with rail_col, st.container(key="home_rail"):
            _markdown(render("home/regime_card.html", card=regime))
            self._render_pulse_card(volume_leaders)
            _markdown(render("home/built_for.html"))

    def _render_pulse_card(self, volume_leaders: list[str]) -> None:
        """Render the Market Pulse card with its in-app link through to Macro."""
        with st.container(key="home_card_pulse", border=True):
            _markdown(
                render("home/pulse_card.html", rows=self.presenter.pulse_rows(volume_leaders))
            )
            nav_button("Go to macro →", "Macro", key="home_cta_macro")

    def _render_context_cards(self) -> None:
        """Render the three context cards side by side, each owning its call to action."""
        for index, (column, card) in enumerate(
            zip(st.columns(3, gap="small"), self.presenter.context_cards(), strict=True)
        ):
            with column, st.container(key=f"home_card_context_{index}", border=True):
                _markdown(render("home/context_card.html", card=card))
                if card.cta_view:
                    nav_button(card.cta_label, card.cta_view, key=f"home_cta_context_{index}")

    def _bucket_summary_table(
        self, securities: pd.DataFrame, histories: dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Return the universe summary with its direction column rendered as badge markup."""
        summary = self.presenter.bucket_summary(securities, histories)
        if summary.empty:
            return summary
        summary["VS 1D"] = summary["VS 1D"].map(_direction_badge_html)
        return summary


def _direction_badge_html(net: int) -> str:
    badge = DirectionBadge.from_net(int(net))
    return render("home/direction_badge.html", net=badge.net, label=badge.label)


def _hero_image_src() -> str:
    """Return the hero artwork as a data URI, falling back to the inline SVG chart."""
    if HERO_IMAGE_PATH.exists():
        encoded = base64.b64encode(HERO_IMAGE_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return f"data:image/svg+xml;utf8,{quote(render('home/hero_fallback.svg'))}"


def _markdown(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)
