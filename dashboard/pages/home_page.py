from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from urllib.parse import quote

import pandas as pd
import streamlit as st

from config import normalize_asset_class
from dashboard.components import DashboardTable
from dashboard.perf import timed_block


@dataclass(frozen=True)
class SnapshotTile:
    label: str
    sublabel: str
    value: str
    delta: str
    delta_class: str
    indicator: str


class HomePage:
    """Render the redesigned homepage and market framing layer."""

    HERO_IMAGE_PATH = Path("dashboard/assets/home_hero.png")

    SNAPSHOT_FEATURES = {
        "UST_10Y_LEVEL": "US 10Y",
        "UST_2Y_LEVEL": "US 2Y",
        "HY_OAS_LEVEL": "HY OAS",
        "IG_OAS_LEVEL": "IG OAS",
        "UST_2S10S": "2s10s",
        "BEI_5Y": "5Y BEI",
        "FEDFUNDS_LEVEL": "Fed Funds",
    }

    def __init__(self, price_store, macro_feature_store):
        self.price_store = price_store
        self.macro_feature_store = macro_feature_store
        self.table = DashboardTable()

    def render(self, securities: pd.DataFrame) -> None:
        with timed_block("home.latest_market_date"):
            latest_market_date = self._latest_market_date(securities)
        with timed_block("home.bucket_summary"):
            bucket_summary = self._build_bucket_summary(securities)
        with timed_block("home.market_snapshot"):
            snapshot_tiles = self._build_market_snapshot_tiles()
        with timed_block("home.regime"):
            regime = self._market_regime(snapshot_tiles)
        with timed_block("home.volume_leaders"):
            volume_leaders = self._top_volume_names(securities)

        latest_date_label = latest_market_date if latest_market_date else "Awaiting history sync"
        market_strip = self._market_snapshot_html(snapshot_tiles, latest_date_label)
        regime_html = self._regime_card_html(regime)
        stat_cards_html = self._stat_cards_html(
            active_etfs=len(securities),
            bucket_count=len(bucket_summary.index),
            latest_date=latest_date_label,
        )
        pulse_html = self._pulse_card_html(volume_leaders)
        context_cards_html = self._context_cards_html(regime)
        built_for_html = self._built_for_card_html()

        st.markdown(market_strip, unsafe_allow_html=True)

        hero_col, regime_col = st.columns([2.3, 1.0], vertical_alignment="top")
        with hero_col:
            st.markdown(self._hero_html(), unsafe_allow_html=True)
        with regime_col:
            st.markdown(regime_html, unsafe_allow_html=True)

        main_left, main_right = st.columns([1.95, 1.05], vertical_alignment="top")
        with main_left:
            st.markdown(stat_cards_html, unsafe_allow_html=True)
            st.markdown(context_cards_html, unsafe_allow_html=True)
            st.markdown('<div class="home-section-title">Universe Snapshot</div>', unsafe_allow_html=True)
            self.table.render(bucket_summary, hide_index=True, height=270)
        with main_right:
            st.markdown(pulse_html, unsafe_allow_html=True)
            st.markdown(built_for_html, unsafe_allow_html=True)

    def _latest_market_date(self, securities: pd.DataFrame) -> str | None:
        tickers = securities["ticker"].astype(str).tolist() if not securities.empty else []
        latest_dates = self.price_store.get_latest_stored_dates(tickers)
        if not latest_dates:
            return None
        return max(latest_dates.values())

    def _build_market_snapshot_tiles(self) -> list[SnapshotTile]:
        feature_names = list(self.SNAPSHOT_FEATURES.keys())
        matrix = self.macro_feature_store.get_feature_matrix(feature_names=feature_names)
        if matrix.empty:
            return []

        tiles: list[SnapshotTile] = []
        for feature_name, label in self.SNAPSHOT_FEATURES.items():
            if feature_name not in matrix.columns:
                continue
            series = matrix[feature_name].dropna()
            if series.empty:
                continue
            latest = float(series.iloc[-1])
            previous = float(series.iloc[-2]) if len(series) > 1 else latest
            delta = latest - previous
            delta_class = "home-delta-flat"
            if delta > 0:
                delta_class = "home-delta-up"
            elif delta < 0:
                delta_class = "home-delta-down"
            tiles.append(
                SnapshotTile(
                    label=label,
                    sublabel=self._snapshot_sublabel(feature_name),
                    value=self._format_snapshot_value(feature_name, latest),
                    delta=self._format_snapshot_delta(feature_name, delta),
                    delta_class=delta_class,
                    indicator="▲" if delta > 0 else "▼" if delta < 0 else "•",
                )
            )
        return tiles

    def _market_regime(self, snapshot_tiles: list[SnapshotTile]) -> dict[str, str | float]:
        tile_map = {tile.label: tile for tile in snapshot_tiles}

        def numeric_delta(label: str) -> float:
            tile = tile_map.get(label)
            if tile is None:
                return 0.0
            raw = tile.delta.replace("bp", "").replace("%", "").replace("+", "").strip()
            raw = raw.replace("−", "-")
            try:
                return float(raw)
            except ValueError:
                return 0.0

        hy_move = numeric_delta("HY OAS")
        ig_move = numeric_delta("IG OAS")
        curve_move = numeric_delta("2s10s")

        score = 0
        if hy_move > 1.5:
            score -= 1
        elif hy_move < -1.0:
            score += 1
        if ig_move > 1.0:
            score -= 1
        elif ig_move < -1.0:
            score += 1
        if curve_move > 1.0:
            score += 1
        elif curve_move < -1.0:
            score -= 1

        if score <= -1:
            return {
                "label": "Risk Off",
                "accent": "#FF5A36",
                "body": "Liquidity is tightening and credit is leaning defensive across the fixed-income complex.",
                "position": 12.0,
            }
        if score >= 1:
            return {
                "label": "Risk On",
                "accent": "#00C176",
                "body": "Rates and spread conditions are leaning constructive, with a more supportive tone for carry.",
                "position": 88.0,
            }
        return {
            "label": "Neutral",
            "accent": "#FFD166",
            "body": "Signals are mixed. Keep the focus on relative value and execution quality rather than a broad macro chase.",
            "position": 50.0,
        }

    def _top_volume_names(self, securities: pd.DataFrame) -> list[str]:
        tickers = securities["ticker"].astype(str).tolist() if not securities.empty else []
        if not tickers:
            return []

        latest_dates = self.price_store.get_latest_stored_dates(tickers)
        if not latest_dates:
            return []

        start_date = min(latest_dates.values())
        histories = self.price_store.get_multi_ticker_price_history(tickers, start_date=start_date)
        ranking: list[tuple[str, float]] = []
        for ticker, history in histories.items():
            if history.empty or "volume" not in history.columns:
                continue
            volume_series = history["volume"].dropna()
            if volume_series.empty:
                continue
            latest = float(volume_series.iloc[-1])
            baseline = float(volume_series.tail(30).mean()) if len(volume_series) >= 1 else latest
            ratio = 0.0 if baseline == 0 else latest / baseline
            ranking.append((ticker, ratio))

        ranking.sort(key=lambda item: item[1], reverse=True)
        return [f"{ticker} ({ratio:.2f}x)" for ticker, ratio in ranking[:4]]

    def _build_bucket_summary(self, securities: pd.DataFrame) -> pd.DataFrame:
        if securities.empty:
            return pd.DataFrame(columns=["ASSET CLASS", "ETF COUNT", "EXAMPLE TICKERS"])

        working_frame = securities.copy()
        working_frame["asset_class"] = (
            working_frame["asset_class"]
            .fillna("Other")
            .astype(str)
            .str.strip()
            .map(normalize_asset_class)
        )

        latest_dates = self.price_store.get_latest_stored_dates(working_frame["ticker"].astype(str).tolist())
        histories = self.price_store.get_multi_ticker_price_history(list(latest_dates.keys()), start_date=None)

        direction_map: dict[str, int] = {}
        for ticker, history in histories.items():
            closes = history.get("close")
            if closes is None:
                direction_map[ticker] = 0
                continue
            close_series = closes.dropna()
            if len(close_series) < 2:
                direction_map[ticker] = 0
                continue
            direction_map[ticker] = int(close_series.iloc[-1] > close_series.iloc[-2]) - int(close_series.iloc[-1] < close_series.iloc[-2])

        grouped = (
            working_frame.groupby("asset_class", dropna=False)["ticker"]
            .agg(
                ETF_COUNT="count",
                EXAMPLE_TICKERS=lambda values: ", ".join(list(values)[:4]),
                VS_1D=lambda values: int(sum(direction_map.get(str(value), 0) for value in values)),
            )
            .reset_index()
            .rename(columns={"asset_class": "ASSET CLASS"})
            .sort_values(["ETF_COUNT", "ASSET CLASS"], ascending=[False, True])
            .reset_index(drop=True)
        )
        grouped["ETF COUNT"] = grouped["ETF_COUNT"].astype(int)
        grouped = grouped.rename(columns={"EXAMPLE_TICKERS": "EXAMPLE TICKERS"})
        grouped["VS 1D"] = grouped["VS_1D"].map(self._format_vs_1d)
        return grouped[["ASSET CLASS", "ETF COUNT", "EXAMPLE TICKERS", "VS 1D"]]

    def _format_vs_1d(self, value: int) -> str:
        if value > 0:
            label = "Broad" if value >= 2 else "Firm"
            return f'<span class="home-table-up">▲ {value}</span> <span class="home-table-note">{label}</span>'
        if value < 0:
            label = "Weakening" if value <= -2 else "Soft"
            return f'<span class="home-table-down">▼ {abs(value)}</span> <span class="home-table-note">{label}</span>'
        return '<span class="home-table-flat">—</span> <span class="home-table-note">Stable</span>'

    def _format_snapshot_value(self, feature_name: str, value: float) -> str:
        if "OAS" in feature_name and "MINUS" not in feature_name:
            return f"{value * 100:.0f}bp"
        if feature_name in {"UST_10Y_LEVEL", "UST_2Y_LEVEL", "FEDFUNDS_LEVEL", "BEI_5Y"}:
            return f"{value:.2f}%"
        if feature_name == "UST_2S10S":
            return f"{value * 100:.0f}bp"
        return f"{value:.2f}"

    def _format_snapshot_delta(self, feature_name: str, delta: float) -> str:
        if "OAS" in feature_name:
            return f"{delta * 100:+.1f}bp"
        if feature_name == "UST_2S10S":
            return f"{delta * 100:+.1f}bp"
        return f"{delta:+.2f}"

    def _snapshot_sublabel(self, feature_name: str) -> str:
        mapping = {
            "UST_10Y_LEVEL": "UST",
            "UST_2Y_LEVEL": "UST",
            "HY_OAS_LEVEL": "Spread",
            "IG_OAS_LEVEL": "Spread",
            "UST_2S10S": "Curve",
            "BEI_5Y": "Inflation",
            "FEDFUNDS_LEVEL": "Policy",
        }
        return mapping.get(feature_name, "Macro")

    def _market_snapshot_html(self, tiles: list[SnapshotTile], latest_date_label: str) -> str:
        cells = [
            dedent(
                """
                <div class="home-strip-primary">
                    <div class="home-strip-kicker">Market Snapshot <span class="home-live-chip">LIVE</span></div>
                    <div class="home-strip-sub">As of {latest_date}</div>
                </div>
                """
            ).strip().format(latest_date=latest_date_label)
        ]
        for tile in tiles[:7]:
            cells.append(
                dedent(
                    f"""
                    <div class="home-strip-cell">
                        <div class="home-strip-label">{tile.label}</div>
                        <div class="home-strip-mini">{tile.sublabel}</div>
                        <div class="home-strip-value-row">
                            <div class="home-strip-value">{tile.value}</div>
                            <div class="home-strip-delta {tile.delta_class}">{tile.indicator} {tile.delta}</div>
                        </div>
                    </div>
                    """
                ).strip()
            )
        return f'<div class="home-market-strip">{"".join(cells)}</div>'

    def _hero_html(self) -> str:
        hero_src = self._hero_image_src()
        return dedent(
            f"""
            <div class="home-hero">
                <div class="home-hero-copy">
                    <div class="home-eyebrow">Opening Market Screen</div>
                    <div class="home-hero-title">Welcome to ETF Terminal</div>
                    <div class="home-hero-body">
                        Your fixed income ETF analytics hub for liquidity, relative value,
                        market structure, and cross-market regime insights.
                    </div>
                    <div class="home-decision-strip">
                        <div class="home-decision-label">Focus Today</div>
                        <div class="home-decision-value">→ Defensive Credit | Long Duration</div>
                    </div>
                    <div class="home-tag-row">
                        <span class="home-signal-tag home-signal-tag--alert">Risk Off</span>
                        <span class="home-signal-tag">Defensive</span>
                        <span class="home-signal-tag">Duration Leading</span>
                        <span class="home-signal-tag">Liquidity Tight</span>
                    </div>
                    <a class="home-inline-link" href="?view=dashboard" target="_self">Open dashboard →</a>
                </div>
                <div class="home-hero-canvas" style="background-image:url('{hero_src}');"></div>
            </div>
            """
        ).strip()

    def _hero_image_src(self) -> str:
        if self.HERO_IMAGE_PATH.exists():
            encoded = base64.b64encode(self.HERO_IMAGE_PATH.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{encoded}"
        hero_svg = quote(self._hero_svg_markup())
        return f"data:image/svg+xml;utf8,{hero_svg}"

    def _hero_svg_markup(self) -> str:
        return dedent(
            """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 260" preserveAspectRatio="none">
                <defs>
                    <linearGradient id="cyanFade" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stop-color="#14CCE9" stop-opacity="0.95"/>
                        <stop offset="100%" stop-color="#14CCE9" stop-opacity="0.45"/>
                    </linearGradient>
                    <linearGradient id="orangeFade" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stop-color="#FF9F1A" stop-opacity="0.9"/>
                        <stop offset="100%" stop-color="#FF9F1A" stop-opacity="0.42"/>
                    </linearGradient>
                    <pattern id="homeGrid" width="48" height="36" patternUnits="userSpaceOnUse">
                        <path d="M 48 0 L 0 0 0 36" fill="none" stroke="#1c2024" stroke-width="1"/>
                    </pattern>
                    <filter id="softGlow">
                        <feGaussianBlur stdDeviation="2" result="blur"/>
                        <feMerge>
                            <feMergeNode in="blur"/>
                            <feMergeNode in="SourceGraphic"/>
                        </feMerge>
                    </filter>
                </defs>
                <rect x="0" y="0" width="900" height="260" fill="#0A0D0F"/>
                <rect x="0" y="0" width="900" height="260" fill="url(#homeGrid)"/>
                <line x1="58" y1="18" x2="58" y2="236" stroke="#2a2e33" stroke-width="1"/>
                <line x1="58" y1="236" x2="882" y2="236" stroke="#2a2e33" stroke-width="1"/>

                <path d="M0,40 C100,34 160,40 240,48 C360,58 430,72 520,86 C620,102 705,118 780,138 C840,152 875,164 900,172"
                      fill="none" stroke="url(#cyanFade)" stroke-width="3.2" stroke-dasharray="7 4" filter="url(#softGlow)"/>
                <path d="M0,145 C90,130 145,120 210,116 C320,108 395,96 470,92 C560,88 635,92 710,98 C785,102 850,106 900,110"
                      fill="none" stroke="url(#orangeFade)" stroke-width="2.3" stroke-dasharray="6 4"/>
                <path d="M0,182 C120,176 180,176 255,178 C340,180 420,184 510,188 C620,192 730,202 810,212 C850,218 875,224 900,230"
                      fill="none" stroke="#1499B2" stroke-opacity="0.55" stroke-width="2.1" stroke-dasharray="8 5"/>

                <g fill="#FF9F1A" opacity="0.75">
                    <circle cx="64" cy="132" r="2.6"/><circle cx="98" cy="132" r="2.6"/><circle cx="132" cy="132" r="2.6"/>
                    <circle cx="166" cy="132" r="2.6"/><circle cx="200" cy="132" r="2.6"/><circle cx="234" cy="132" r="2.6"/>
                    <circle cx="268" cy="132" r="2.6"/><circle cx="302" cy="132" r="2.6"/><circle cx="336" cy="132" r="2.6"/>
                    <circle cx="370" cy="132" r="2.6"/><circle cx="404" cy="132" r="2.6"/><circle cx="438" cy="132" r="2.6"/>
                    <circle cx="472" cy="132" r="2.6"/><circle cx="506" cy="132" r="2.6"/><circle cx="540" cy="132" r="2.6"/>
                    <circle cx="574" cy="132" r="2.6"/><circle cx="608" cy="132" r="2.6"/><circle cx="642" cy="132" r="2.6"/>
                    <circle cx="676" cy="132" r="2.6"/><circle cx="710" cy="132" r="2.6"/><circle cx="744" cy="132" r="2.6"/>
                    <circle cx="778" cy="132" r="2.6"/><circle cx="812" cy="132" r="2.6"/><circle cx="846" cy="132" r="2.6"/>
                </g>

                <g fill="#14CCE9" fill-opacity="0.62">
                    <circle cx="78" cy="176" r="2.3"/><circle cx="114" cy="176" r="2.3"/><circle cx="150" cy="176" r="2.3"/>
                    <circle cx="186" cy="176" r="2.3"/><circle cx="222" cy="176" r="2.3"/><circle cx="258" cy="176" r="2.3"/>
                    <circle cx="294" cy="176" r="2.3"/><circle cx="330" cy="176" r="2.3"/><circle cx="366" cy="176" r="2.3"/>
                    <circle cx="402" cy="176" r="2.3"/><circle cx="438" cy="176" r="2.3"/><circle cx="474" cy="176" r="2.3"/>
                    <circle cx="510" cy="176" r="2.3"/><circle cx="546" cy="176" r="2.3"/><circle cx="582" cy="176" r="2.3"/>
                    <circle cx="618" cy="176" r="2.3"/><circle cx="654" cy="176" r="2.3"/><circle cx="690" cy="176" r="2.3"/>
                    <circle cx="726" cy="176" r="2.3"/><circle cx="762" cy="176" r="2.3"/><circle cx="798" cy="176" r="2.3"/>
                    <circle cx="834" cy="176" r="2.3"/>
                </g>

                <g opacity="0.9">
                    <rect x="272" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                    <rect x="302" y="34" width="4" height="216" fill="#FF9F1A" fill-opacity="0.28"/>
                    <rect x="370" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                    <rect x="400" y="34" width="4" height="216" fill="#FF9F1A" fill-opacity="0.28"/>
                    <rect x="468" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                    <rect x="498" y="34" width="4" height="216" fill="#FF9F1A" fill-opacity="0.28"/>
                    <rect x="566" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                    <rect x="596" y="34" width="4" height="216" fill="#FF9F1A" fill-opacity="0.28"/>
                    <rect x="664" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                    <rect x="694" y="34" width="4" height="216" fill="#FF9F1A" fill-opacity="0.28"/>
                    <rect x="762" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                    <rect x="792" y="34" width="4" height="216" fill="#FF9F1A" fill-opacity="0.28"/>
                    <rect x="860" y="34" width="4" height="216" fill="#14CCE9" fill-opacity="0.36"/>
                </g>
            </svg>
            """
        ).strip()

    def _regime_card_html(self, regime: dict[str, str | float]) -> str:
        position = float(regime["position"])
        return dedent(
            f"""
            <div class="home-regime-card">
                <div class="home-panel-kicker">Market Regime Indicator</div>
                <div class="home-regime-label" style="color:{regime['accent']};">{regime['label']}</div>
                <div class="home-regime-body">{regime['body']}</div>
                <div class="home-regime-scale">
                    <div class="home-regime-scale-bar"></div>
                    <div class="home-regime-scale-marker" style="left:calc({position}% - 6px);"></div>
                </div>
                <div class="home-regime-legend">
                    <span>Risk Off</span>
                    <span>Neutral</span>
                    <span>Risk On</span>
                </div>
            </div>
            """
        ).strip()

    def _stat_cards_html(self, *, active_etfs: int, bucket_count: int, latest_date: str) -> str:
        active_icon = """
        <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
            <rect x="5" y="18" width="4.5" height="8" rx="0.6"></rect>
            <rect x="13.5" y="12" width="4.5" height="14" rx="0.6"></rect>
            <rect x="22" y="6" width="4.5" height="20" rx="0.6"></rect>
        </svg>
        """
        bucket_icon = """
        <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
            <path d="M6 7.5h12.5a2 2 0 0 1 2 2V13a2 2 0 0 1-2 2H10v3.5h10.5a2 2 0 0 1 2 2V24a2 2 0 0 1-2 2H6.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square" stroke-linejoin="miter"/>
            <path d="M6 7.5V26" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"/>
        </svg>
        """
        calendar_icon = """
        <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false">
            <rect x="5" y="7.5" width="22" height="19" rx="2" fill="none" stroke="currentColor" stroke-width="2.1"/>
            <path d="M5 12.5h22" fill="none" stroke="currentColor" stroke-width="2.1"/>
            <path d="M10 5v5M22 5v5" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="square"/>
            <circle cx="10.5" cy="17" r="1.15" fill="currentColor"/>
            <circle cx="16" cy="17" r="1.15" fill="currentColor"/>
            <circle cx="21.5" cy="17" r="1.15" fill="currentColor"/>
            <circle cx="10.5" cy="22" r="1.15" fill="currentColor"/>
            <circle cx="16" cy="22" r="1.15" fill="currentColor"/>
            <circle cx="21.5" cy="22" r="1.15" fill="currentColor"/>
        </svg>
        """
        return dedent(
            f"""
            <div class="home-stat-grid">
                <div class="home-stat-card">
                    <div class="home-stat-icon">{active_icon}</div>
                    <div>
                        <div class="home-stat-label">Active ETFs</div>
                        <div class="home-stat-value">{active_etfs}</div>
                        <div class="home-stat-note">+2 vs last week</div>
                    </div>
                </div>
                <div class="home-stat-card">
                    <div class="home-stat-icon">{bucket_icon}</div>
                    <div>
                        <div class="home-stat-label">Universe Buckets</div>
                        <div class="home-stat-value">{bucket_count}</div>
                        <div class="home-stat-note">Stable grouping mix</div>
                    </div>
                </div>
                <div class="home-stat-card">
                    <div class="home-stat-icon">{calendar_icon}</div>
                    <div>
                        <div class="home-stat-label">Latest Market Date</div>
                        <div class="home-stat-value home-stat-value--date">{latest_date}</div>
                        <div class="home-stat-note">Refreshed and aligned</div>
                    </div>
                </div>
            </div>
            """
        ).strip()

    def _pulse_card_html(self, volume_leaders: list[str]) -> str:
        items = volume_leaders or ["LQD (1.18x)", "TLT (1.07x)", "HYG (1.04x)", "MUB (0.96x)"]
        pulse_rows = [
            ("Rates", "Belly leadership", "WATCH", "elevated"),
            ("Credit", "IG vs HY beta", "CONFIRM", "mixed"),
            ("Liquidity", "Volume vs 30D", "NORMAL", "active"),
            ("Flows", "Defensive bias", "ELEVATED", "neutral"),
        ]
        rows = "".join(
            dedent(
                f"""
                <div class="home-pulse-row">
                    <div class="home-pulse-icon">↗</div>
                    <div class="home-pulse-text"><strong>{title}</strong>: {body}</div>
                    <div class="home-pulse-tag home-pulse-tag--{tag_class}">{tag}</div>
                </div>
                """
            ).strip()
            for title, body, tag, tag_class in pulse_rows
        )
        return dedent(
            f"""
            <div class="home-side-card">
                <div class="home-panel-kicker">Market Pulse</div>
                <div class="home-side-title">Morning framing</div>
                <div class="home-tag-row home-tag-row--tight">
                    <span class="home-signal-tag home-signal-tag--alert">Risk Off</span>
                    <span class="home-signal-tag">Credit Weakening</span>
                </div>
                <div class="home-pulse-list">{rows}</div>
                <a class="home-inline-link home-inline-link--small" href="?view=macro" target="_self">Go to macro →</a>
            </div>
            """
        ).strip()

    def _context_cards_html(self, regime: dict[str, str | float]) -> str:
        return dedent(
            f"""
            <div class="home-context-grid">
                <div class="home-context-card">
                    <div class="home-panel-kicker">Project Overview</div>
                    <div class="home-context-title">A focused terminal for fixed income ETF decision support</div>
                    <div class="home-context-body">
                        ETF Terminal organizes price action, liquidity, and relative-value signals
                        for bond ETF markets in one place. The workflow starts with a market framing
                        layer, then moves into security-level analysis and RV follow-through.
                    </div>
                    <div class="home-inline-link">Learn more →</div>
                </div>
                <div class="home-context-card">
                    <div class="home-panel-kicker">Morning Setup</div>
                    <div class="home-context-title">What the homepage should help you answer quickly</div>
                    <div class="home-context-body">
                        Where is duration leading? Is credit trading defensively or constructively?
                        Which ETFs are showing unusual participation? Where are the cleanest
                        relative-value dislocations?
                    </div>
                    <div class="home-inline-link">See morning checklist →</div>
                </div>
                <div class="home-context-card">
                    <div class="home-panel-kicker">News Layer</div>
                    <div class="home-context-title">Proposed homepage news section</div>
                    <div class="home-context-body">
                        This area can hold a concise market brief with five to eight headlines
                        across rates, credit, ETF flow, and macro events. We can start with a
                        manual note, then move to a live feed.
                    </div>
                    <div class="home-inline-link">View latest news →</div>
                </div>
            </div>
            """
        ).strip()

    def _built_for_card_html(self) -> str:
        return dedent(
            """
            <div class="home-built-card">
                <div class="home-built-icon">◎</div>
                <div>
                    <div class="home-built-title">Built for fixed-income workflow</div>
                    <div class="home-built-body">
                        Move from market framing into security analysis without losing context
                        across rates, spreads, and execution conditions.
                    </div>
                </div>
            </div>
            """
        ).strip()
