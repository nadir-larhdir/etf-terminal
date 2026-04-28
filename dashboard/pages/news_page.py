"""News page — Bloomberg-style market brief for the fixed income ETF terminal."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.cache import (
    app_cache_key,
    cached_feature_matrix,
    cached_latest_feature_values,
)
from dashboard.perf import timed_block
from services.news import NewsFeedService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BUCKET_COLORS: dict[str, str] = {
    "rates": "#5F8D84",
    "credit": "#6F7B46",
    "macro": "#A55C45",
    "etfs": "#4A7BA8",
    "policy": "#7B6BA8",
    "inflation": "#C4882A",
    "earnings": "#8B7355",
}

_BUCKET_LABELS: dict[str, str] = {
    "rates": "Rates",
    "credit": "Credit",
    "macro": "Macro",
    "etfs": "ETFs",
    "policy": "Policy",
    "inflation": "Inflation",
}

# Keyword → bucket mapping for classifier
_BUCKET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "etfs": ("etf", "fund flow", "bond fund", "lqd", "hyg", "tlt", "agg", "bnd", "vcit", "igsb"),
    "policy": ("fomc", "federal reserve", "central bank", "boe", "ecb", "rate decision", "rate cut", "rate hike"),
    "inflation": ("inflation", "cpi", "pce", "breakeven", "tips", "real rate"),
    "rates": ("treasury", "yield", "curve", "auction", "duration", "dgs"),
    "credit": ("credit", "spread", "investment grade", "high yield", "junk", "corporate bond", "oas"),
    "macro": ("gdp", "payroll", "unemployment", "labor", "retail sales", "economy", "economic", "china", "trade"),
}

# Features loaded for sentiment + snapshot bar
_SNAPSHOT_FEATURES: dict[str, tuple[str, str]] = {
    "UST_10Y_LEVEL":    ("10Y UST", "{:.2f}%"),
    "UST_2S10S":        ("2s10s",   "{:.0f}bp"),
    "BEI_5Y":           ("5Y BEI",  "{:.2f}%"),
    "FEDFUNDS_LEVEL":   ("Fed Funds", "{:.2f}%"),
    "IG_OAS_LEVEL":     ("IG OAS",  "{:.0f}bp"),
}

_SENTIMENT_FEATURES = (
    "IG_OAS_Z20", "HY_OAS_Z20", "UST_2S10S_Z20",
    "UST_10Y_CHANGE_20D", "BEI_5Y_CHANGE_20D",
)

_THEME_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "Rate Cut Outlook",
        "feature": "FEDFUNDS_CHANGE_12M",
        "icon": "📉",
        "positive_direction": "down",   # falling = cuts expected = positive for bonds
        "description_fn": lambda v: (
            "Markets price in first cut" if v < -0.1
            else "Rate path uncertain" if abs(v) < 0.1
            else "Further hikes possible"
        ),
        "trend_fn": lambda v: ("Trending", "#6F7B46") if v < -0.1 else ("Mixed", "#A55C45") if abs(v) < 0.1 else ("Hawkish", "#8B2020"),
    },
    {
        "name": "Credit Conditions",
        "feature": "IG_OAS_CHANGE_20D",
        "icon": "📊",
        "positive_direction": "down",   # tightening = improving
        "description_fn": lambda v: (
            "Spreads tighten across IG and HY" if v < -2
            else "Spread conditions stable" if abs(v) < 2
            else "Spreads widening, caution warranted"
        ),
        "trend_fn": lambda v: ("Improving", "#6F7B46") if v < -2 else ("Stable", "#707A68") if abs(v) < 2 else ("Widening", "#A55C45"),
    },
    {
        "name": "Inflation Path",
        "feature": "BEI_5Y_CHANGE_20D",
        "icon": "🔥",
        "positive_direction": "neutral",
        "description_fn": lambda v: (
            "Inflation expectations falling" if v < -0.05
            else "Inflation expectations stable" if abs(v) < 0.05
            else "Inflation expectations rising"
        ),
        "trend_fn": lambda v: ("Easing", "#6F7B46") if v < -0.05 else ("Mixed", "#707A68") if abs(v) < 0.05 else ("Rising", "#A55C45"),
    },
    {
        "name": "Curve Shape",
        "feature": "UST_2S10S",
        "icon": "📈",
        "positive_direction": "up",
        "description_fn": lambda v: (
            f"Curve inverted at {v*100:.0f}bp" if v < 0
            else f"Flat curve at {v*100:.0f}bp" if v < 0.5
            else f"Steepening curve at {v*100:.0f}bp"
        ),
        "trend_fn": lambda v: ("Inverted", "#A55C45") if v < 0 else ("Flat", "#707A68") if v < 0.5 else ("Steepening", "#6F7B46"),
    },
    {
        "name": "Policy Stance",
        "feature": "UST10_MINUS_FEDFUNDS",
        "icon": "🏦",
        "positive_direction": "up",
        "description_fn": lambda v: (
            "Policy restrictive, long-end well-anchored" if v < 0
            else "Policy near neutral" if v < 0.5
            else "Long-end premium over funds rate rising"
        ),
        "trend_fn": lambda v: ("Restrictive", "#A55C45") if v < 0 else ("Neutral", "#707A68") if v < 0.5 else ("Accommodative", "#6F7B46"),
    },
]

# Upcoming events — semi-static; update weekly or wire to an economic calendar API
_UPCOMING_EVENTS: list[dict[str, str]] = [
    {"time": "10:00 ET", "name": "Fed Speaker",        "day": "Today"},
    {"time": "14:00 ET", "name": "2Y Treasury Auction", "day": "Today"},
    {"time": "08:30 ET", "name": "Core PCE (MoM)",     "day": "Tomorrow"},
    {"time": "10:00 ET", "name": "FOMC Rate Decision",  "day": "May 7"},
    {"time": "08:30 ET", "name": "CPI (YoY)",           "day": "May 13"},
]

_MARKET_MOVER_TICKERS = ("TLT", "HYG", "LQD", "SHY", "EMB", "IEF", "AGG", "MBB")

_TICKER_META: dict[str, dict[str, str]] = {
    "TLT": {"name": "iShares 20+ Year Treasury Bond ETF", "bucket": "rates"},
    "HYG": {"name": "iShares iBoxx $ High Yield Corp Bond ETF", "bucket": "credit"},
    "LQD": {"name": "iShares iBoxx $ IG Corp Bond ETF", "bucket": "credit"},
    "SHY": {"name": "iShares 1-3 Year Treasury Bond ETF", "bucket": "rates"},
    "EMB": {"name": "iShares JP Morgan USD EM Bond ETF", "bucket": "credit"},
    "IEF": {"name": "iShares 7-10 Year Treasury Bond ETF", "bucket": "rates"},
    "AGG": {"name": "iShares Core US Aggregate Bond ETF", "bucket": "rates"},
    "MBB": {"name": "iShares MBS ETF", "bucket": "rates"},
}


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def _load_news_feeds(limit_per_feed: int = 8) -> tuple[dict[str, dict], str | None]:
    """Fetch all configured RSS feeds with an hourly cache window."""
    try:
        data = NewsFeedService().fetch_all(limit_per_feed=limit_per_feed)
        return data, None
    except Exception as exc:  # noqa: BLE001
        return {}, str(exc)


@st.cache_data(ttl=900, show_spinner=False)
def _load_market_movers(cache_key: str, _price_store) -> dict[str, dict]:
    """Compute day-over-day returns for key market-mover ETFs."""
    result: dict[str, dict] = {}
    try:
        histories = _price_store.get_multi_ticker_price_history(
            list(_MARKET_MOVER_TICKERS), start_date=None, end_date=None
        )
        for ticker, df in histories.items():
            if df.empty or "adj_close" not in df.columns or len(df) < 2:
                continue
            prev_close = float(df["adj_close"].iloc[-2])
            last_close = float(df["adj_close"].iloc[-1])
            if prev_close <= 0:
                continue
            change_pct = (last_close - prev_close) / prev_close * 100.0
            last_date = str(df.index[-1])[:10]
            result[ticker] = {
                "change_pct": round(change_pct, 2),
                "last_close": round(last_close, 2),
                "as_of": last_date,
            }
    except Exception:  # noqa: BLE001
        pass
    return result


# ---------------------------------------------------------------------------
# Internal helpers (module-level, pure functions)
# ---------------------------------------------------------------------------

def _classify_bucket(title: str) -> str:
    """Classify a headline into the most specific matching bucket."""
    lower = title.lower()
    for bucket, keywords in _BUCKET_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return bucket
    return "macro"


def _relative_time(published_at: str | None) -> str:
    """Return a human-readable relative time string ('3m ago', '2h ago')."""
    if not published_at:
        return ""
    try:
        dt = datetime.fromisoformat(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{delta.days}d ago"
    except (ValueError, TypeError):
        return ""


def _dedupe_items(feed_data: dict[str, dict]) -> list[dict]:
    """Flatten all feed buckets into a single deduplicated list, newest first."""
    seen: set[str] = set()
    items: list[dict] = []
    for bucket in ("rates", "credit", "macro"):
        for item in feed_data.get(bucket, {}).get("items", []):
            key = re.sub(r"\s+", " ", item.get("title", "")).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            items.append({**item, "bucket": _classify_bucket(item.get("title", ""))})
    return items


def _compute_summary_counts(items: list[dict]) -> dict[str, int]:
    """Derive summary stat counts from the deduplicated headline list."""
    cb_keywords = ("fed", "fomc", "boe", "ecb", "central bank", "rate decision")
    macro_keywords = ("gdp", "payroll", "unemployment", "retail", "cpi", "pce", "inflation")
    etf_keywords = ("etf", "fund", "lqd", "hyg", "tlt", "agg")

    cb_count = sum(1 for i in items if any(k in i.get("title", "").lower() for k in cb_keywords))
    macro_count = sum(1 for i in items if i["bucket"] == "macro")
    etf_count = sum(1 for i in items if any(k in i.get("title", "").lower() for k in etf_keywords))
    return {
        "top_stories": min(len(items), 5),
        "market_moving": len(items),
        "etf_mentions": etf_count,
        "central_bank": cb_count,
        "macro_events": macro_count,
        "earnings": 0,
    }


def _compute_sentiment(latest_df: pd.DataFrame) -> tuple[float, str, str]:
    """Return (score, label, description) from macro z-score features.

    Score is clamped to [-1, 1]; positive = constructive for fixed income.
    """
    if latest_df.empty:
        return 0.0, "Neutral", "Insufficient data for sentiment calculation."

    score_map = {"IG_OAS_Z20": -0.4, "HY_OAS_Z20": -0.3, "UST_2S10S_Z20": 0.15,
                 "UST_10Y_CHANGE_20D": -0.1, "BEI_5Y_CHANGE_20D": -0.15}
    total_weight = sum(abs(w) for w in score_map.values())
    score = 0.0

    for _, row in latest_df.iterrows():
        feature = str(row["feature_name"])
        weight = score_map.get(feature, 0.0)
        if weight == 0.0:
            continue
        try:
            raw = float(row["value"])
            # Invert so negative z-score (tightening) = positive for bonds
            score += -raw * weight
        except (TypeError, ValueError):
            pass

    score = max(-1.0, min(1.0, score / total_weight))

    if score < -0.4:
        return score, "Bearish", "Spread widening and rate pressure dominate."
    if score < -0.15:
        return score, "Cautious", "Slightly negative tone across rates and credit."
    if score < 0.15:
        return score, "Neutral", "Mixed signals across rates, credit, and macro."
    if score < 0.4:
        return score, "Balanced", "Slightly positive tone across rates and credit."
    return score, "Constructive", "Tightening spreads and rate stability support bonds."


def _mini_sparkline(series: pd.Series, *, color: str) -> go.Figure:
    """Build a compact, axis-free sparkline figure for theme tracker cards."""
    fig = go.Figure(go.Scatter(
        x=list(range(len(series))),
        y=series.values,
        mode="lines",
        line={"color": color, "width": 1.5},
        fill="tozeroy",
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.08)",
    ))
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=48,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_PAGE_CSS = """
<style>
.news-summary-bar {
    display:flex;gap:1.5rem;align-items:center;padding:0.55rem 0.75rem;
    background:#FBF8F1;border:1px solid #D8D4C7;border-radius:3px;margin-bottom:0.8rem;
}
.news-stat-item { display:flex;flex-direction:column;min-width:70px; }
.news-stat-value { font-size:1.15rem;font-weight:700;color:#1F271C;line-height:1.1; }
.news-stat-label { font-size:0.68rem;color:#707A68;text-transform:uppercase;letter-spacing:0.4px; }
.news-stat-divider { width:1px;height:36px;background:#D8D4C7;flex-shrink:0; }
.news-stat-update { margin-left:auto;text-align:right; }
.news-tag {
    display:inline-block;padding:0.10rem 0.36rem;border-radius:1px;
    font-size:0.64rem;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;
    border:1px solid currentColor;margin-right:0.4rem;
}
.news-section-header {
    font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.7px;
    color:#1F271C;border-bottom:2px solid #1F271C;padding-bottom:0.30rem;margin-bottom:0.55rem;
}
.news-section-header-link {
    font-size:0.68rem;font-weight:500;text-transform:uppercase;letter-spacing:0.4px;
    color:#6F7B46 !important;text-decoration:none !important;float:right;
}
.news-item {
    display:flex;align-items:flex-start;gap:0.55rem;padding:0.55rem 0;
    border-bottom:1px solid #E8E4D8;
}
.news-item-meta { font-size:0.68rem;color:#707A68;white-space:nowrap;min-width:56px;margin-top:2px; }
.news-item-body { flex:1;min-width:0; }
.news-item-title {
    color:#1F271C !important;font-size:0.88rem;font-weight:500;line-height:1.35;
    text-decoration:none !important;display:block;margin-bottom:0.15rem;
}
.news-item-title:hover { color:#6F7B46 !important; }
.news-item-source { font-size:0.72rem;color:#707A68; }
.news-bm { color:#C9C4B4;font-size:0.80rem;cursor:pointer;flex-shrink:0;margin-top:2px; }
.top-story-card {
    background:#FBF8F1;border:1px solid #D8D4C7;border-radius:3px;
    padding:1.2rem;margin-bottom:0.7rem;position:relative;
}
.top-story-title {
    font-size:1.25rem;font-weight:700;color:#1F271C !important;line-height:1.3;
    text-decoration:none !important;display:block;margin:0.55rem 0 0.5rem 0;
}
.top-story-title:hover { color:#6F7B46 !important; }
.top-story-desc { font-size:0.88rem;color:#4F5A49;line-height:1.5;margin-bottom:0.55rem; }
.top-story-footer { font-size:0.75rem;color:#707A68;display:flex;gap:0.5rem;align-items:center; }
.mover-card {
    padding:0.6rem 0.7rem;border:1px solid #D8D4C7;background:#FBF8F1;
    border-radius:3px;margin-bottom:0.5rem;display:flex;gap:0.6rem;align-items:flex-start;
}
.mover-ticker { font-size:0.95rem;font-weight:700;color:#1F271C;min-width:36px; }
.mover-name { font-size:0.72rem;color:#707A68;margin-top:1px; }
.mover-desc { font-size:0.78rem;color:#4F5A49;margin-top:0.25rem; }
.mover-change-pos { font-size:0.92rem;font-weight:700;color:#4E7B52;white-space:nowrap; }
.mover-change-neg { font-size:0.92rem;font-weight:700;color:#A55C45;white-space:nowrap; }
.theme-card {
    border:1px solid #D8D4C7;background:#FBF8F1;border-radius:3px;
    padding:0.65rem 0.75rem;height:100%;
}
.theme-name { font-size:0.80rem;font-weight:700;color:#1F271C;margin-bottom:0.20rem; }
.theme-trend { font-size:0.70rem;font-weight:700;text-transform:uppercase;margin-bottom:0.20rem; }
.theme-desc { font-size:0.72rem;color:#4F5A49;line-height:1.4; }
.sidebar-section-header {
    font-size:0.70rem;font-weight:700;text-transform:uppercase;letter-spacing:0.65px;
    color:#1F271C;border-bottom:1px solid #D8D4C7;padding-bottom:0.25rem;margin-bottom:0.45rem;
}
.filter-row {
    display:flex;justify-content:space-between;align-items:center;
    padding:0.35rem 0.40rem;cursor:pointer;border-radius:2px;margin-bottom:2px;
    font-size:0.80rem;
}
.filter-row:hover { background:#F0EDE4; }
.filter-row-active { background:#1F271C;color:#FBF8F1;border-radius:2px; }
.filter-count {
    font-size:0.72rem;background:#D8D4C7;color:#1F271C;padding:0.08rem 0.36rem;
    border-radius:8px;font-weight:700;
}
.filter-count-active { background:#6F7B46;color:#FBF8F1; }
.sentiment-bar-wrap { position:relative;height:8px;border-radius:4px;margin:0.5rem 0 0.25rem 0;
    background:linear-gradient(to right,#A55C45,#D8D4C7 50%,#4E7B52); }
.sentiment-bar-indicator {
    position:absolute;top:-3px;width:14px;height:14px;border-radius:50%;
    background:#1F271C;border:2px solid #FBF8F1;transform:translateX(-50%);
    box-shadow:0 1px 3px rgba(0,0,0,0.2);
}
.sentiment-labels {
    display:flex;justify-content:space-between;font-size:0.65rem;color:#707A68;
}
.event-row {
    display:flex;justify-content:space-between;align-items:center;
    padding:0.32rem 0;border-bottom:1px solid #E8E4D8;font-size:0.78rem;
}
.event-time { color:#707A68;font-size:0.70rem;min-width:58px; }
.event-name { color:#1F271C;font-weight:500;flex:1; }
.event-day { color:#707A68;font-size:0.70rem; }
.source-row {
    display:flex;justify-content:space-between;align-items:center;
    padding:0.28rem 0;border-bottom:1px solid #E8E4D8;
}
.source-name { font-size:0.78rem;color:#1F271C;font-weight:500; }
.source-count { font-size:0.72rem;color:#707A68; }
a { text-decoration:none !important; color:inherit !important; }

/* Filter buttons — base reset, shared across all bucket containers */
.st-key-filter_all button,
.st-key-filter_rates button,
.st-key-filter_credit button,
.st-key-filter_macro button,
.st-key-filter_etfs button,
.st-key-filter_policy button,
.st-key-filter_inflation button {
    background:transparent !important;border:none !important;box-shadow:none !important;
    color:#1F271C !important;font-size:0.80rem !important;font-weight:400 !important;
    padding:0.30rem 0.40rem !important;border-radius:2px !important;
    width:100% !important;text-align:left !important;justify-content:flex-start !important;
    margin-bottom:1px !important;cursor:pointer !important;font-family:inherit !important;
    display:flex !important;align-items:center !important;
}
.st-key-filter_all button:hover,
.st-key-filter_rates button:hover,
.st-key-filter_credit button:hover,
.st-key-filter_macro button:hover,
.st-key-filter_etfs button:hover,
.st-key-filter_policy button:hover,
.st-key-filter_inflation button:hover { background:#F0EDE4 !important; }
/* Colored dot via ::before — one per bucket */
.st-key-filter_rates button::before   { content:"● "; color:#5F8D84; flex-shrink:0; }
.st-key-filter_credit button::before  { content:"● "; color:#6F7B46; flex-shrink:0; }
.st-key-filter_macro button::before   { content:"● "; color:#A55C45; flex-shrink:0; }
.st-key-filter_etfs button::before    { content:"● "; color:#4A7BA8; flex-shrink:0; }
.st-key-filter_policy button::before  { content:"● "; color:#7B6BA8; flex-shrink:0; }
.st-key-filter_inflation button::before { content:"● "; color:#C4882A; flex-shrink:0; }
.news-active-filter-chip {
    display:inline-flex;align-items:center;gap:0.35rem;
    background:#1F271C;color:#FBF8F1;font-size:0.72rem;font-weight:600;
    text-transform:uppercase;letter-spacing:0.4px;padding:0.18rem 0.55rem;
    border-radius:2px;margin-bottom:0.65rem;
}
</style>
"""


# ---------------------------------------------------------------------------
# NewsPage class
# ---------------------------------------------------------------------------

class NewsPage:
    """Render the Bloomberg-style News page for the fixed income ETF terminal.

    Accepts an optional price_store for the Market Movers section.
    All sections degrade gracefully when data is unavailable.
    """

    def __init__(self, macro_feature_store, price_store=None) -> None:
        self.macro_feature_store = macro_feature_store
        self.price_store = price_store

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Render the full news page: summary bar, main content, and sidebar."""
        st.markdown(_PAGE_CSS, unsafe_allow_html=True)

        with timed_block("news.load"):
            feed_data, feed_error = _load_news_feeds(limit_per_feed=10)
            all_items = _dedupe_items(feed_data)

        active_filters: set[str] = st.session_state.get("news_filter_buckets", set())
        display_items = (
            [item for item in all_items if item.get("bucket") in active_filters]
            if active_filters
            else all_items
        )

        counts = _compute_summary_counts(all_items)
        now_str = datetime.now().strftime("%H:%M ET")

        self._render_summary_bar(counts, now_str)

        if feed_error:
            st.warning(f"Live feed unavailable: {feed_error}")

        main_col, sidebar_col = st.columns([7, 3], gap="large")

        with main_col:
            if active_filters:
                chips = "".join(
                    f"<span class='news-active-filter-chip' style='border-left:3px solid {_BUCKET_COLORS.get(b, '#707A68')};margin-right:0.3rem;'>"
                    f"<span style='color:{_BUCKET_COLORS.get(b, '#707A68')};'>●</span> {_BUCKET_LABELS.get(b, b.title())}"
                    f"</span>"
                    for b in sorted(active_filters)
                )
                st.markdown(
                    f"<div style='display:flex;flex-wrap:wrap;gap:0.3rem;align-items:center;margin-bottom:0.65rem;'>"
                    f"{chips}"
                    f"<span style='font-size:0.72rem;color:#707A68;'>— click active filter to remove</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            self._render_top_story(display_items)
            self._render_latest_news(display_items)
            self._render_market_movers()
            self._render_theme_tracker()

        with sidebar_col:
            self._render_news_filters(all_items)
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            self._render_sentiment_indicator()
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            self._render_upcoming_events()
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            self._render_news_sources(all_items)

    # ------------------------------------------------------------------
    # Summary bar
    # ------------------------------------------------------------------

    def _render_summary_bar(self, counts: dict[str, int], now_str: str) -> None:
        """Render the top summary stat bar with headline counts and timestamp."""
        stats = [
            (counts["top_stories"], "Top Stories"),
            (counts["market_moving"], "Market Moving"),
            (counts["etf_mentions"], "ETF Mentions"),
            (counts["central_bank"], "Central Bank"),
            (counts["macro_events"], "Macro Events"),
            (counts["earnings"], "Earnings"),
        ]
        parts = ["<div class='news-summary-bar'>"]
        parts.append(
            "<div class='news-stat-item'>"
            "<div style='font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#707A68;'>News Summary</div>"
            f"<div style='font-size:0.68rem;color:#707A68;'>As of {now_str}</div>"
            "</div><div class='news-stat-divider'></div>"
        )
        for value, label in stats:
            parts.append(
                f"<div class='news-stat-item'>"
                f"<div class='news-stat-value'>{value}</div>"
                f"<div class='news-stat-label'>{label}</div>"
                f"</div>"
            )
        parts.append(
            "<div class='news-stat-divider'></div>"
            "<div class='news-stat-item news-stat-update'>"
            "<div style='font-size:0.68rem;color:#707A68;'>Latest Update</div>"
            f"<div style='font-size:0.82rem;font-weight:700;color:#1F271C;'>{now_str}</div>"
            "</div>"
        )
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Top story
    # ------------------------------------------------------------------

    def _render_top_story(self, items: list[dict]) -> None:
        """Render the featured top-story card with title, description excerpt, and source."""
        if not items:
            return

        st.markdown(
            "<div class='news-section-header'>Top Stories</div>",
            unsafe_allow_html=True,
        )

        story = items[0]
        bucket = story.get("bucket", "macro")
        color = _BUCKET_COLORS.get(bucket, "#707A68")
        label = _BUCKET_LABELS.get(bucket, bucket.title())
        time_str = _relative_time(story.get("published_at"))
        source = story.get("source", "")
        title = story.get("title", "")
        link = story.get("link", "#")

        # Build an excerpt from the title words as a pseudo-description
        words = title.split()
        excerpt = " ".join(words[:18]) + ("…" if len(words) > 18 else "")

        tag_html = f"<span class='news-tag' style='color:{color};border-color:{color};'>{label}</span>"
        time_html = f"<span style='font-size:0.72rem;color:#707A68;'>{time_str}</span>" if time_str else ""

        st.markdown(
            f"""
            <div class='top-story-card'>
                <div style='display:flex;align-items:center;gap:0.5rem;margin-bottom:0.1rem;'>
                    {tag_html}{time_html}
                </div>
                <a href='{link}' target='_blank' rel='noopener noreferrer' class='top-story-title'><span style='color:{color};'>{title}</span></a>
                <div class='top-story-desc'>{excerpt}</div>
                <div class='top-story-footer'>
                    <span>{source}</span>
                    <span style='color:#D8D4C7;'>|</span>
                    <span>🔖</span>
                    <span>↗</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Latest news list
    # ------------------------------------------------------------------

    def _render_latest_news(self, items: list[dict], max_items: int = 8) -> None:
        """Render the chronological Latest News list with time, tag, title, source."""
        if not items:
            return

        st.markdown(
            "<div class='news-section-header'>Latest News</div>",
            unsafe_allow_html=True,
        )

        rows_html: list[str] = []
        for item in items[1: max_items + 1]:
            bucket = item.get("bucket", "macro")
            color = _BUCKET_COLORS.get(bucket, "#707A68")
            label = _BUCKET_LABELS.get(bucket, bucket.title())
            time_str = _relative_time(item.get("published_at"))
            source = item.get("source", "")
            title = item.get("title", "")
            link = item.get("link", "#")

            rows_html.append(
                f"<div class='news-item'>"
                f"<div class='news-item-meta'>{time_str}</div>"
                f"<div class='news-item-body'>"
                f"<span class='news-tag' style='color:{color};border-color:{color};'>{label}</span>"
                f"<a href='{link}' target='_blank' rel='noopener noreferrer' class='news-item-title'><span style='color:{color};'>{title}</span></a>"
                f"<div class='news-item-source'>{source}</div>"
                f"</div>"
                f"<div class='news-bm'>🔖</div>"
                f"</div>"
            )

        st.markdown(
            "<div>" + "".join(rows_html) + "</div>"
            "<div style='font-size:0.78rem;color:#6F7B46;margin-top:0.55rem;cursor:pointer;font-weight:600;'>"
            "View all latest news →</div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Market movers
    # ------------------------------------------------------------------

    def _render_market_movers(self) -> None:
        """Render the Market Movers section using price store day-over-day returns."""
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='news-section-header'>Market Movers"
            "<a href='#' class='news-section-header-link'>View all →</a>"
            "</div>",
            unsafe_allow_html=True,
        )

        if self.price_store is None:
            st.caption("Price store not connected — market movers unavailable.")
            return

        cache_key = app_cache_key(self.price_store.engine)
        with timed_block("news.market_movers"):
            movers = _load_market_movers(cache_key, self.price_store)

        if not movers:
            st.caption("Price data not yet available for market movers.")
            return

        # Sort by absolute return, show top 5
        sorted_movers = sorted(movers.items(), key=lambda kv: abs(kv[1]["change_pct"]), reverse=True)[:5]

        for ticker, data in sorted_movers:
            meta = _TICKER_META.get(ticker, {"name": ticker, "bucket": "rates"})
            bucket = meta["bucket"]
            color = _BUCKET_COLORS.get(bucket, "#707A68")
            label = _BUCKET_LABELS.get(bucket, bucket.title())
            change = data["change_pct"]
            change_class = "mover-change-pos" if change >= 0 else "mover-change-neg"
            arrow = "▲" if change >= 0 else "▼"
            as_of = data["as_of"][5:]  # MM-DD

            st.markdown(
                f"<div class='mover-card'>"
                f"<div style='flex:1'>"
                f"<div style='display:flex;align-items:center;gap:0.4rem;'>"
                f"<span class='mover-ticker'>{ticker}</span>"
                f"<span class='news-tag' style='color:{color};border-color:{color};'>{label}</span>"
                f"</div>"
                f"<div class='mover-name'>{meta['name']}</div>"
                f"</div>"
                f"<div style='text-align:right;flex-shrink:0;'>"
                f"<div class='{change_class}'>{arrow} {abs(change):.2f}%</div>"
                f"<div style='font-size:0.68rem;color:#707A68;'>{as_of}</div>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            "<div style='font-size:0.78rem;color:#6F7B46;margin-top:0.35rem;font-weight:600;cursor:pointer;'>"
            "View all market movers →</div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Theme tracker
    # ------------------------------------------------------------------

    def _render_theme_tracker(self) -> None:
        """Render the Theme Tracker section with sparklines from macro feature history."""
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='news-section-header'>Theme Tracker</div>",
            unsafe_allow_html=True,
        )

        feature_names = tuple(t["feature"] for t in _THEME_CONFIGS)
        cache_key = app_cache_key(self.macro_feature_store.engine)
        start_date = pd.Timestamp.now() - pd.Timedelta(days=60)

        with timed_block("news.theme_tracker"):
            matrix = cached_feature_matrix(
                cache_key,
                feature_names,
                str(start_date.date()),
                None,
                self.macro_feature_store,
            )
            latest_df = cached_latest_feature_values(
                cache_key,
                feature_names,
                self.macro_feature_store,
            )

        latest_map: dict[str, float] = {}
        if not latest_df.empty:
            for _, row in latest_df.iterrows():
                try:
                    latest_map[str(row["feature_name"])] = float(row["value"])
                except (TypeError, ValueError):
                    pass

        cols = st.columns(len(_THEME_CONFIGS))
        for col, theme in zip(cols, _THEME_CONFIGS):
            feature = theme["feature"]
            value = latest_map.get(feature)

            if value is None:
                with col:
                    st.markdown(
                        f"<div class='theme-card'>"
                        f"<div style='font-size:1.1rem;'>{theme['icon']}</div>"
                        f"<div class='theme-name'>{theme['name']}</div>"
                        f"<div style='font-size:0.70rem;color:#707A68;'>No data</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                continue

            trend_label, trend_color = theme["trend_fn"](value)
            description = theme["description_fn"](value)

            with col:
                st.markdown(
                    f"<div class='theme-card'>"
                    f"<div style='font-size:1.1rem;'>{theme['icon']}</div>"
                    f"<div class='theme-name'>{theme['name']}</div>"
                    f"<div class='theme-trend' style='color:{trend_color};'>{trend_label}</div>"
                    f"<div class='theme-desc'>{description}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if not matrix.empty and feature in matrix.columns:
                    series = matrix[feature].dropna().tail(30)
                    if len(series) >= 3:
                        st.plotly_chart(
                            _mini_sparkline(series, color=trend_color),
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )

        st.markdown(
            "<div style='font-size:0.72rem;color:#6F7B46;margin-top:0.35rem;cursor:pointer;'>"
            "How themes are calculated →</div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Sidebar: news filters
    # ------------------------------------------------------------------

    def _render_news_filters(self, items: list[dict]) -> None:
        """Render sidebar News Filters as styled interactive buttons supporting multi-select."""
        bucket_counts: dict[str, int] = {}
        for item in items:
            b = item.get("bucket", "macro")
            bucket_counts[b] = bucket_counts.get(b, 0) + 1

        total = len(items)
        active_filters: set[str] = st.session_state.get("news_filter_buckets", set())

        st.markdown("<div class='sidebar-section-header'>News Filters</div>", unsafe_allow_html=True)

        filters = [("all", "All News", total)] + [
            (b, _BUCKET_LABELS.get(b, b.title()), bucket_counts.get(b, 0))
            for b in ("rates", "credit", "macro", "etfs", "policy", "inflation")
            if bucket_counts.get(b, 0) > 0
        ]

        for bucket_key, display_label, count in filters:
            is_active = (bucket_key == "all" and not active_filters) or (bucket_key in active_filters)

            with st.container(key=f"filter_{bucket_key}"):
                if is_active:
                    # Inject active-state override into this container's scoped CSS class
                    st.markdown(
                        f"<style>"
                        f".st-key-filter_{bucket_key} button{{"
                        f"background:#1F271C !important;color:#FBF8F1 !important;font-weight:600 !important;"
                        f"}}"
                        f".st-key-filter_{bucket_key} button:hover{{background:#2E3B29 !important;}}"
                        f".st-key-filter_{bucket_key} button::before{{color:rgba(251,248,241,0.65) !important;}}"
                        f"</style>",
                        unsafe_allow_html=True,
                    )

                if st.button(f"{display_label}  ({count})", key=f"nf_{bucket_key}", use_container_width=True):
                    new_buckets = set(active_filters)
                    if bucket_key == "all":
                        new_buckets.clear()
                    elif bucket_key in new_buckets:
                        new_buckets.discard(bucket_key)
                    else:
                        new_buckets.add(bucket_key)
                    st.session_state["news_filter_buckets"] = new_buckets
                    st.rerun()

    # ------------------------------------------------------------------
    # Sidebar: sentiment indicator
    # ------------------------------------------------------------------

    def _render_sentiment_indicator(self) -> None:
        """Render the Sentiment Indicator derived from macro z-score features."""
        st.markdown(
            "<div class='sidebar-section-header'>Sentiment Indicator "
            "<span style='font-size:0.68rem;color:#707A68;cursor:help;' title='Computed from OAS z-scores, curve shape, and rate momentum'>ⓘ</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        cache_key = app_cache_key(self.macro_feature_store.engine)
        with timed_block("news.sentiment"):
            latest_df = cached_latest_feature_values(
                cache_key,
                tuple(sorted(_SENTIMENT_FEATURES)),
                self.macro_feature_store,
            )

        score, label, description = _compute_sentiment(latest_df)
        # Map score [-1, 1] to position [0%, 100%]
        position_pct = max(2, min(98, int((score + 1) / 2 * 100)))

        label_color = "#4E7B52" if score > 0.15 else "#A55C45" if score < -0.15 else "#707A68"

        st.markdown(
            f"<div style='font-size:1.0rem;font-weight:700;color:{label_color};margin-bottom:0.15rem;'>{label}</div>"
            f"<div style='font-size:0.75rem;color:#4F5A49;margin-bottom:0.45rem;'>{description}</div>"
            f"<div class='sentiment-bar-wrap'>"
            f"<div class='sentiment-bar-indicator' style='left:{position_pct}%;'></div>"
            f"</div>"
            f"<div class='sentiment-labels'><span>Negative</span><span>Neutral</span><span>Positive</span></div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Sidebar: upcoming events
    # ------------------------------------------------------------------

    def _render_upcoming_events(self) -> None:
        """Render the Upcoming Events list from the static event schedule."""
        st.markdown(
            "<div class='sidebar-section-header'>Upcoming Events"
            "<a href='#' style='float:right;font-size:0.68rem;color:#6F7B46;font-weight:600;'>View calendar →</a>"
            "</div>",
            unsafe_allow_html=True,
        )

        rows = "".join(
            f"<div class='event-row'>"
            f"<span class='event-time'>{ev['time']}</span>"
            f"<span class='event-name'>{ev['name']}</span>"
            f"<span class='event-day'>{ev['day']}</span>"
            f"</div>"
            for ev in _UPCOMING_EVENTS
        )
        st.markdown(f"<div>{rows}</div>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # Sidebar: news sources
    # ------------------------------------------------------------------

    def _render_news_sources(self, items: list[dict]) -> None:
        """Render the News Sources breakdown derived from feed item source fields."""
        st.markdown(
            "<div class='sidebar-section-header'>News Sources"
            "<a href='#' style='float:right;font-size:0.68rem;color:#6F7B46;font-weight:600;'>Manage →</a>"
            "</div>",
            unsafe_allow_html=True,
        )

        source_counts: dict[str, int] = {}
        for item in items:
            src = (item.get("source") or "Unknown").strip()
            source_counts[src] = source_counts.get(src, 0) + 1

        top_sources = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]

        rows = "".join(
            f"<div class='source-row'>"
            f"<span class='source-name'>{src}</span>"
            f"<span class='source-count'>{count}</span>"
            f"</div>"
            for src, count in top_sources
        )
        st.markdown(
            f"<div>{rows}</div>"
            "<div style='font-size:0.75rem;color:#6F7B46;margin-top:0.45rem;font-weight:600;cursor:pointer;'>"
            "View all sources →</div>",
            unsafe_allow_html=True,
        )
