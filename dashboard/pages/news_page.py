"""News page — Bloomberg-style market brief for the fixed income ETF terminal."""

from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
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

_BUCKET_BACKGROUND_COLORS: dict[str, str] = {
    "all": "#E8EDE3",
    "rates": "#DCEBE8",
    "credit": "#E6EBCF",
    "macro": "#F0DCD5",
    "etfs": "#DCE9F4",
    "policy": "#E7DFF0",
    "inflation": "#F3E4C8",
}

_SOURCE_LOGO_DIR = Path(__file__).resolve().parent.parent / "assets" / "logos"
_SOURCE_LOGOS: dict[str, str] = {
    "Investopedia": "investopedia.ico",
    "Reuters": "reuters.ico",
    "MSN": "msn.ico",
    "Seeking Alpha": "seeking-alpha.ico",
    "24/7 Wall St.": "247-wall-st.png",
    "Advisor Perspectives": "advisor-perspectives.png",
}
_SOURCE_LOGO_MIME_TYPES: dict[str, str] = {
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

_BUCKET_LABELS: dict[str, str] = {
    "rates": "Rates",
    "credit": "Credit",
    "macro": "Macro",
    "etfs": "ETF",
    "policy": "Policy",
    "inflation": "Inflation",
}

_FILTER_ICON_SVGS: dict[str, str] = {
    "all": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <rect x="4" y="4" width="6" height="6" rx="1"/>
            <rect x="14" y="4" width="6" height="6" rx="1"/>
            <rect x="4" y="14" width="6" height="6" rx="1"/>
            <rect x="14" y="14" width="6" height="6" rx="1"/>
        </svg>
    """,
    "rates": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 17h16"/>
            <path d="M5 15l4-4 4 2 6-7"/>
            <path d="M16 6h3v3"/>
        </svg>
    """,
    "credit": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 9c4-.5 8-.5 16 0"/>
            <path d="M4 15c5 .5 10 .5 16-1"/>
        </svg>
    """,
    "macro": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="8"/>
            <path d="M4 12h16"/>
            <path d="M12 4c2 2.2 3 4.8 3 8s-1 5.8-3 8"/>
            <path d="M12 4c-2 2.2-3 4.8-3 8s1 5.8 3 8"/>
        </svg>
    """,
    "etfs": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 4v8h8"/>
            <path d="M20 12a8 8 0 1 1-8-8"/>
            <path d="M15.5 5.1a8 8 0 0 1 4.4 4.4"/>
        </svg>
    """,
    "policy": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 10h16"/>
            <path d="M6 10v7"/>
            <path d="M10 10v7"/>
            <path d="M14 10v7"/>
            <path d="M18 10v7"/>
            <path d="M3 19h18"/>
            <path d="M12 4l8 4H4z"/>
        </svg>
    """,
    "inflation": """
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
             stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 13V7a2 2 0 0 1 2-2h6l6 6-8 8-6-6z"/>
            <path d="M8.5 8.5h.01"/>
            <path d="M12 15l4-4"/>
            <path d="M16 11h-3"/>
            <path d="M16 11v3"/>
        </svg>
    """,
}

_THEME_ICON_SVGS: dict[str, str] = {
    "rate_cut": """
        <svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M5 18h14"/>
            <path d="M6 14l4-4 3 2 5-6"/>
            <path d="M16 6h2v2"/>
            <path d="M7 5v5"/>
            <path d="M9 5v5"/>
        </svg>
    """,
    "credit": """
        <svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M5 8c4-.5 8-.5 14 0"/>
            <path d="M5 13c5 .5 9 .5 14-.5"/>
            <path d="M5 18c5 1 10 1 14-.8"/>
        </svg>
    """,
    "inflation": """
        <svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M6 18L18 6"/>
            <circle cx="7.5" cy="7.5" r="1.7"/>
            <circle cx="16.5" cy="16.5" r="1.7"/>
            <path d="M14 6h4v4"/>
        </svg>
    """,
    "curve": """
        <svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M4 17c2-6 7-10 16-10"/>
        </svg>
    """,
    "policy": """
        <svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M4 10h16"/>
            <path d="M6 10v7"/>
            <path d="M10 10v7"/>
            <path d="M14 10v7"/>
            <path d="M18 10v7"/>
            <path d="M3 19h18"/>
            <path d="M12 4l8 4H4z"/>
        </svg>
    """,
}

_FIXED_INCOME_ETF_TERMS: tuple[str, ...] = (
    "bond",
    "fixed income",
    "treasury",
    "corporate",
    "credit",
    "income",
    "high yield",
    "investment grade",
    "municipal",
    "muni",
    "duration",
    "lqd",
    "hyg",
    "jnk",
    "tlt",
    "agg",
    "bnd",
    "vcit",
    "igsb",
    "istb",
)

# Keyword → bucket mapping for classifier
_BUCKET_KEYWORDS: dict[str, tuple[str, ...]] = {
    "policy": (
        "fomc",
        "federal reserve",
        "central bank",
        "boe",
        "ecb",
        "rate decision",
        "rate cut",
        "rate hike",
    ),
    "inflation": ("inflation", "cpi", "pce", "breakeven", "tips", "real rate"),
    "rates": ("treasury", "yield", "curve", "auction", "duration", "dgs"),
    "credit": (
        "credit",
        "spread",
        "spreads",
        "compression",
        "widening",
        "tightening",
        "investment grade",
        "high yield",
        "leveraged loan",
        "junk",
        "corporate bond",
        "default swap",
        "cds",
        "cdx",
        "oas",
    ),
    "macro": (
        "gdp",
        "payroll",
        "unemployment",
        "labor",
        "retail sales",
        "economy",
        "economic",
        "china",
        "trade",
    ),
}

# Features loaded for sentiment + snapshot bar
_SNAPSHOT_FEATURES: dict[str, tuple[str, str]] = {
    "UST_10Y_LEVEL": ("10Y UST", "{:.2f}%"),
    "UST_2S10S": ("2s10s", "{:.0f}bp"),
    "BEI_5Y": ("5Y BEI", "{:.2f}%"),
    "FEDFUNDS_LEVEL": ("Fed Funds", "{:.2f}%"),
    "IG_OAS_LEVEL": ("IG OAS", "{:.0f}bp"),
}

_SENTIMENT_FEATURES = (
    "IG_OAS_Z20",
    "HY_OAS_Z20",
    "UST_2S10S_Z20",
    "UST_10Y_CHANGE_20D",
    "BEI_5Y_CHANGE_20D",
)

_THEME_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "Rate Cut Outlook",
        "feature": "FEDFUNDS_CHANGE_12M",
        "icon": "rate_cut",
        "color": _BUCKET_COLORS["rates"],
        "positive_direction": "down",  # falling = cuts expected = positive for bonds
        "description_fn": lambda v: (
            "Markets price in first cut"
            if v < -0.1
            else "Rate path uncertain" if abs(v) < 0.1 else "Further hikes possible"
        ),
        "trend_fn": lambda v: (
            ("Trending", "#6F7B46")
            if v < -0.1
            else ("Mixed", "#A55C45") if abs(v) < 0.1 else ("Hawkish", "#8B2020")
        ),
    },
    {
        "name": "Credit Conditions",
        "feature": "IG_OAS_CHANGE_20D",
        "icon": "credit",
        "color": _BUCKET_COLORS["credit"],
        "positive_direction": "down",  # tightening = improving
        "description_fn": lambda v: (
            "Spreads tighten across IG and HY"
            if v < -2
            else "Spread conditions stable" if abs(v) < 2 else "Spreads widening, caution warranted"
        ),
        "trend_fn": lambda v: (
            ("Improving", "#6F7B46")
            if v < -2
            else ("Stable", "#707A68") if abs(v) < 2 else ("Widening", "#A55C45")
        ),
    },
    {
        "name": "Inflation Path",
        "feature": "BEI_5Y_CHANGE_20D",
        "icon": "inflation",
        "color": _BUCKET_COLORS["inflation"],
        "positive_direction": "neutral",
        "description_fn": lambda v: (
            "Inflation expectations falling"
            if v < -0.05
            else (
                "Inflation expectations stable"
                if abs(v) < 0.05
                else "Inflation expectations rising"
            )
        ),
        "trend_fn": lambda v: (
            ("Easing", "#6F7B46")
            if v < -0.05
            else ("Mixed", "#707A68") if abs(v) < 0.05 else ("Rising", "#A55C45")
        ),
    },
    {
        "name": "Curve Shape",
        "feature": "UST_2S10S",
        "icon": "curve",
        "color": _BUCKET_COLORS["rates"],
        "positive_direction": "up",
        "description_fn": lambda v: (
            f"Curve inverted at {v*100:.0f}bp"
            if v < 0
            else f"Flat curve at {v*100:.0f}bp" if v < 0.5 else f"Steepening curve at {v*100:.0f}bp"
        ),
        "trend_fn": lambda v: (
            ("Inverted", "#A55C45")
            if v < 0
            else ("Flat", "#707A68") if v < 0.5 else ("Steepening", "#6F7B46")
        ),
    },
    {
        "name": "Policy Stance",
        "feature": "UST10_MINUS_FEDFUNDS",
        "icon": "policy",
        "color": _BUCKET_COLORS["policy"],
        "positive_direction": "up",
        "description_fn": lambda v: (
            "Policy restrictive, long-end well-anchored"
            if v < 0
            else "Policy near neutral" if v < 0.5 else "Long-end premium over funds rate rising"
        ),
        "trend_fn": lambda v: (
            ("Restrictive", "#A55C45")
            if v < 0
            else ("Neutral", "#707A68") if v < 0.5 else ("Accommodative", "#6F7B46")
        ),
    },
]

# Upcoming events — semi-static; update weekly or wire to an economic calendar API
_UPCOMING_EVENTS: list[dict[str, str]] = [
    {"time": "10:00 ET", "name": "Fed Speaker", "day": "Today"},
    {"time": "14:00 ET", "name": "2Y Treasury Auction", "day": "Today"},
    {"time": "08:30 ET", "name": "Core PCE (MoM)", "day": "Tomorrow"},
    {"time": "10:00 ET", "name": "FOMC Rate Decision", "day": "May 7"},
    {"time": "08:30 ET", "name": "CPI (YoY)", "day": "May 13"},
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
    if "etf" in lower and any(term in lower for term in _FIXED_INCOME_ETF_TERMS):
        return "etfs"
    for bucket, keywords in _BUCKET_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return bucket
    return "macro"


def _svg_data_uri(svg: str) -> str:
    """Return a CSS-safe data URI for a compact inline SVG icon."""
    return "data:image/svg+xml," + quote(re.sub(r"\s+", " ", svg.strip()), safe=":/?&=,;-.%")


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Convert a #RRGGBB color to RGB components."""
    clean = color.lstrip("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def _theme_icon_html(icon_key: str, color: str) -> str:
    """Return an inline line icon for a theme tracker card."""
    svg = _THEME_ICON_SVGS.get(icon_key, _THEME_ICON_SVGS["curve"]).format(color=color)
    return f"<span class='theme-icon'>{svg}</span>"


def _source_logo_file(source_name: str) -> str | None:
    """Return the mapped logo file for a source name."""
    normalized = source_name.strip().lower()
    for source, filename in _SOURCE_LOGOS.items():
        source_key = source.lower()
        if source_key in normalized or (source == "24/7 Wall St." and "wall st" in normalized):
            return filename
    return None


def _source_logo_data_uri(filename: str) -> str | None:
    """Return a data URI for a source logo asset if it exists."""
    logo_path = _SOURCE_LOGO_DIR / filename
    if not logo_path.exists():
        return None
    mime_type = _SOURCE_LOGO_MIME_TYPES.get(logo_path.suffix.lower(), "application/octet-stream")
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _source_logo_fallback_html(source_name: str) -> str:
    """Return a compact initials fallback when a real source logo is unavailable."""
    initials = "".join(part[0] for part in re.findall(r"[A-Za-z0-9]+", source_name)[:2]).upper()
    return f"<span class='source-logo-wrap source-logo-fallback'>{escape(initials or '?')}</span>"


def _source_logo_html(source_name: str) -> str:
    """Return a fixed-size real logo image for the News Sources list."""
    filename = _source_logo_file(source_name)
    logo_src = _source_logo_data_uri(filename) if filename else None
    if not logo_src:
        return _source_logo_fallback_html(source_name)

    safe_name = escape(source_name)
    return (
        "<span class='source-logo-wrap'>"
        f"<img src='{logo_src}' alt='{safe_name} logo' class='source-logo' loading='lazy' />"
        "</span>"
    )


def _relative_time(published_at: str | None) -> str:
    """Return a human-readable relative time string ('3m ago', '2h ago')."""
    if not published_at:
        return ""
    try:
        dt = datetime.fromisoformat(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - dt
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
    for bucket in ("rates", "credit", "etfs", "macro"):
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

    score_map = {
        "IG_OAS_Z20": -0.4,
        "HY_OAS_Z20": -0.3,
        "UST_2S10S_Z20": 0.15,
        "UST_10Y_CHANGE_20D": -0.1,
        "BEI_5Y_CHANGE_20D": -0.15,
    }
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


def _mini_sparkline_svg(series: pd.Series, *, color: str) -> str:
    """Build an inline SVG sparkline for theme tracker cards."""
    values = [float(v) for v in series.dropna().tail(30).values]
    if len(values) < 2:
        return "<div class='theme-sparkline-empty'>No trend</div>"

    width, height = 220, 62
    pad_x, pad_y = 3, 7
    min_v, max_v = min(values), max(values)
    span = max(max_v - min_v, 1e-9)
    step = (width - pad_x * 2) / (len(values) - 1)

    points: list[str] = []
    for idx, value in enumerate(values):
        x = pad_x + idx * step
        y = pad_y + (1 - ((value - min_v) / span)) * (height - pad_y * 2)
        points.append(f"{x:.1f},{y:.1f}")

    baseline = height - 4
    area_points = f"{pad_x},{baseline} " + " ".join(points) + f" {width - pad_x},{baseline}"
    r, g, b = _hex_to_rgb(color)

    return (
        "<svg class='theme-sparkline' viewBox='0 0 220 62' preserveAspectRatio='none' aria-hidden='true'>"
        f"<polygon points='{area_points}' fill='rgba({r},{g},{b},0.10)'/>"
        f"<polyline points='{' '.join(points)}' fill='none' stroke='{color}' stroke-width='2.1' "
        "stroke-linecap='round' stroke-linejoin='round'/>"
        f"<circle cx='{points[-1].split(',')[0]}' cy='{points[-1].split(',')[1]}' r='2.5' fill='{color}'/>"
        "</svg>"
    )


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_PAGE_CSS = """
<style>
:root {
    --news-bg: var(--etf-bg-elevated, #FBF8F1);
    --news-panel: var(--etf-bg-panel, #F8F5EE);
    --news-ink: var(--etf-ink, #1F271C);
    --news-soft: var(--etf-ink-soft, #4F5A49);
    --news-muted: var(--etf-ink-muted, #707A68);
    --news-border: var(--etf-border, #D8D4C7);
    --news-border-strong: var(--etf-border-strong, #C9C4B4);
    --news-accent: var(--etf-accent, #6F7B46);
}
.news-summary-bar {
    display:flex;gap:1.5rem;align-items:center;padding:0.55rem 0.75rem;
    background:var(--news-bg);border:1px solid var(--news-border);border-radius:1px;margin-bottom:0.8rem;
}
.news-stat-item { display:flex;flex-direction:column;min-width:70px; }
.news-stat-value { font-size:0.96rem;font-weight:700;color:var(--news-ink);line-height:1.15;letter-spacing:0.12px; }
.news-stat-label { font-size:0.68rem;color:var(--news-muted);text-transform:uppercase;letter-spacing:0.42px; }
.news-stat-divider { width:1px;height:36px;background:var(--news-border);flex-shrink:0; }
.news-stat-update { margin-left:auto;text-align:right; }
.news-tag {
    display:inline-block;padding:0.10rem 0.36rem;border-radius:1px;
    font-size:0.62rem;font-weight:700;text-transform:uppercase;letter-spacing:0.42px;
    border:1px solid currentColor;margin-right:0.4rem;
}
.news-section-header {
    font-size:0.8rem;font-weight:700;text-transform:uppercase;letter-spacing:0.42px;
    color:var(--news-ink);border-bottom:1px solid var(--news-border);
    padding-bottom:0.35rem;margin:0.25rem 0 0.60rem 0;
}
.news-section-header-link {
    font-size:0.62rem;font-weight:700;text-transform:uppercase;letter-spacing:0.34px;
    color:var(--news-accent) !important;text-decoration:none !important;float:right;
}
.news-item {
    display:flex;align-items:flex-start;gap:0.55rem;padding:0.55rem 0;
    border-bottom:1px solid rgba(216,212,199,0.70);
}
.news-item-meta { font-size:0.68rem;color:var(--news-muted);white-space:nowrap;min-width:56px;margin-top:2px; }
.news-item-body { flex:1;min-width:0; }
.news-item-title {
    color:var(--news-ink) !important;font-size:0.82rem;font-weight:600;line-height:1.35;
    text-decoration:none !important;display:block;margin-bottom:0.15rem;
}
.news-item-title:hover { color:var(--news-accent) !important; }
.news-item-source { font-size:0.68rem;color:var(--news-muted); }
.news-bm { color:var(--news-border-strong);font-size:0.80rem;flex-shrink:0;margin-top:2px; }
.top-story-card {
    background:var(--news-bg);border:1px solid var(--news-border);border-radius:1px;
    padding:1.2rem;margin-bottom:0.7rem;position:relative;
}
.top-story-title {
    font-size:1.08rem;font-weight:700;color:var(--news-ink) !important;line-height:1.25;
    letter-spacing:0.12px;text-transform:uppercase;
    text-decoration:none !important;display:block;margin:0.55rem 0 0.5rem 0;
}
.top-story-title:hover { color:var(--news-accent) !important; }
.top-story-desc { font-size:0.78rem;color:var(--news-soft);line-height:1.45;margin-bottom:0.55rem; }
.top-story-footer { font-size:0.72rem;color:var(--news-muted);display:flex;gap:0.5rem;align-items:center; }
.mover-card {
    padding:0.6rem 0.7rem;border:1px solid var(--news-border);background:var(--news-bg);
    border-radius:1px;margin-bottom:0.5rem;display:flex;gap:0.6rem;align-items:flex-start;
}
.mover-ticker { font-size:0.88rem;font-weight:700;color:var(--news-ink);min-width:36px;letter-spacing:0.1px; }
.mover-name { font-size:0.68rem;color:var(--news-muted);margin-top:1px; }
.mover-desc { font-size:0.78rem;color:var(--news-soft);margin-top:0.25rem; }
.mover-change-pos { font-size:0.92rem;font-weight:700;color:#4E7B52;white-space:nowrap; }
.mover-change-neg { font-size:0.92rem;font-weight:700;color:#A55C45;white-space:nowrap; }
.theme-tracker-band {
    background:linear-gradient(180deg,rgba(248,245,238,0.96),rgba(251,248,241,0.78));
    border-top:1px solid rgba(216,212,199,0.70);border-bottom:1px solid rgba(216,212,199,0.70);
    margin-top:0.75rem;padding:1rem 0 1.15rem 0;
}
.theme-tracker-head {
    display:flex;align-items:center;gap:0.42rem;margin-bottom:0.25rem;
}
.theme-tracker-title {
    font-size:0.8rem;font-weight:700;text-transform:uppercase;letter-spacing:0.42px;color:var(--news-ink);
}
.theme-info {
    width:15px;height:15px;border:1px solid var(--news-muted);border-radius:50%;
    color:var(--news-muted);font-size:0.62rem;font-weight:700;display:inline-flex;
    align-items:center;justify-content:center;line-height:1;
}
.theme-tracker-subtitle {
    font-size:0.76rem;color:var(--news-muted);line-height:1.4;margin-bottom:0.8rem;
}
.theme-grid {
    display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0.72rem;
}
.theme-card {
    border:1px solid var(--news-border);background:rgba(251,248,241,0.88);border-radius:4px;
    padding:0.78rem 0.72rem 0.68rem 0.72rem;min-height:178px;display:flex;flex-direction:column;
    box-shadow:inset 3px 0 0 var(--theme-color),0 1px 2px rgba(31,39,28,0.04);
}
.theme-card:hover {
    background:linear-gradient(180deg,var(--theme-bg),rgba(251,248,241,0.92));
}
.theme-icon {
    width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;margin-bottom:0.48rem;
    color:var(--theme-color);
}
.theme-icon svg { width:30px;height:30px;display:block; }
.theme-name {
    font-size:0.74rem;font-weight:700;color:var(--news-ink);margin-bottom:0.42rem;
    text-transform:uppercase;letter-spacing:0.30px;line-height:1.2;
}
.theme-trend {
    align-self:flex-start;font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:0.34px;
    color:var(--theme-color);background:var(--theme-bg);border-radius:999px;padding:0.14rem 0.42rem;margin-bottom:0.48rem;
}
.theme-desc { font-size:0.72rem;color:var(--news-soft);line-height:1.35;min-height:38px;margin-bottom:0.5rem; }
.theme-sparkline-wrap { margin-top:auto;height:62px;width:100%; }
.theme-sparkline { width:100%;height:62px;display:block;overflow:visible; }
.theme-sparkline-empty {
    height:62px;display:flex;align-items:center;color:var(--news-muted);font-size:0.68rem;
}
@media (max-width: 1200px) {
    .theme-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
}
@media (max-width: 760px) {
    .theme-grid { grid-template-columns:1fr; }
}
.sidebar-section-header {
    font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.42px;
    color:var(--news-ink);border-bottom:1px solid var(--news-border);padding-bottom:0.35rem;margin-bottom:0.45rem;
}
.st-key-filter_all, .st-key-filter_rates, .st-key-filter_credit,
.st-key-filter_macro, .st-key-filter_etfs, .st-key-filter_policy,
.st-key-filter_inflation { margin:0 !important; }
.st-key-filter_all button, .st-key-filter_rates button, .st-key-filter_credit button,
.st-key-filter_macro button, .st-key-filter_etfs button, .st-key-filter_policy button,
.st-key-filter_inflation button {
    background:var(--news-bg) !important;border:none !important;border-radius:0 !important;
    box-shadow:none !important;color:var(--news-ink) !important;display:grid !important;
    grid-template-columns:28px minmax(0,1fr) auto;gap:0.45rem;align-items:center;
    justify-content:stretch !important;justify-items:stretch !important;
    min-height:44px;padding:0 0.72rem !important;text-align:left !important;width:100%;
    font-size:0.78rem !important;font-weight:700 !important;font-family:inherit !important;
    border-left:1px solid var(--news-border) !important;border-right:1px solid var(--news-border) !important;
    border-bottom:1px solid rgba(216,212,199,0.28) !important;
}
.st-key-filter_all button [data-testid="stMarkdownContainer"],
.st-key-filter_rates button [data-testid="stMarkdownContainer"],
.st-key-filter_credit button [data-testid="stMarkdownContainer"],
.st-key-filter_macro button [data-testid="stMarkdownContainer"],
.st-key-filter_etfs button [data-testid="stMarkdownContainer"],
.st-key-filter_policy button [data-testid="stMarkdownContainer"],
.st-key-filter_inflation button [data-testid="stMarkdownContainer"] {
    justify-self:start !important;text-align:left !important;width:100%;
}
.st-key-filter_all button p, .st-key-filter_rates button p, .st-key-filter_credit button p,
.st-key-filter_macro button p, .st-key-filter_etfs button p, .st-key-filter_policy button p,
.st-key-filter_inflation button p {
    margin:0 !important;text-align:left !important;font-size:0.78rem !important;
    font-weight:700 !important;letter-spacing:0.42px;text-transform:uppercase;
}
.st-key-filter_all button {
    border-top:1px solid var(--news-border) !important;border-radius:1px 1px 0 0 !important;
}
.st-key-filter_inflation button {
    border-bottom:1px solid var(--news-border) !important;border-radius:0 0 1px 1px !important;
}
.st-key-filter_all button:hover, .st-key-filter_rates button:hover, .st-key-filter_credit button:hover,
.st-key-filter_macro button:hover, .st-key-filter_etfs button:hover, .st-key-filter_policy button:hover,
.st-key-filter_inflation button:hover { background:rgba(111,123,70,0.08) !important;color:var(--news-ink) !important; }
.st-key-filter_all button::before, .st-key-filter_rates button::before,
.st-key-filter_credit button::before, .st-key-filter_macro button::before,
.st-key-filter_etfs button::before, .st-key-filter_policy button::before,
.st-key-filter_inflation button::before {
    content:"";display:block;width:18px;height:18px;background-repeat:no-repeat;
    background-position:center;background-size:18px 18px;
}
.st-key-filter_all button::after, .st-key-filter_rates button::after,
.st-key-filter_credit button::after, .st-key-filter_macro button::after,
.st-key-filter_etfs button::after, .st-key-filter_policy button::after,
.st-key-filter_inflation button::after {
    justify-self:end;color:var(--news-muted);font-size:0.78rem;font-weight:700;
    font-variant-numeric:tabular-nums;
}
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
    display:grid;grid-template-columns:22px minmax(0,1fr) auto;align-items:center;
    gap:0.44rem;padding:0.30rem 0;border-bottom:1px solid rgba(216,212,199,0.70);
}
.source-row:hover { background:rgba(111,123,70,0.045); }
.source-row:hover .source-logo-wrap { opacity:1; }
.source-logo-wrap {
    width:22px;height:22px;display:flex;align-items:center;justify-content:center;
    flex-shrink:0;opacity:0.86;
}
.source-logo {
    max-width:22px;max-height:22px;width:auto;height:auto;object-fit:contain;
    filter:grayscale(1) saturate(0.45) opacity(0.88);mix-blend-mode:multiply;
}
.source-logo-fallback {
    width:20px;height:20px;border:1px solid var(--news-border-strong);border-radius:50%;
    background:rgba(251,248,241,0.72);color:var(--news-soft);
    font-size:0.54rem;font-weight:700;line-height:1;letter-spacing:0;
}
.source-name {
    font-size:0.76rem;color:var(--news-ink);font-weight:600;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
.source-count {
    font-size:0.72rem;color:var(--news-muted);font-weight:700;
    font-variant-numeric:tabular-nums;justify-self:end;
}
a { text-decoration:none !important; color:inherit !important; }
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
                    f"<span style='font-size:0.68rem;color:var(--news-muted);text-transform:uppercase;letter-spacing:0.34px;'>"
                    f"Toggle filters to combine news types</span>"
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

        tag_html = (
            f"<span class='news-tag' style='color:{color};border-color:{color};'>{label}</span>"
        )
        time_html = (
            f"<span style='font-size:0.72rem;color:#707A68;'>{time_str}</span>" if time_str else ""
        )

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
        for item in items[1 : max_items + 1]:
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
            "<div>" + "".join(rows_html) + "</div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Market movers
    # ------------------------------------------------------------------

    def _render_market_movers(self) -> None:
        """Render the Market Movers section using price store day-over-day returns."""
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='news-section-header'>Market Movers</div>",
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
        sorted_movers = sorted(
            movers.items(), key=lambda kv: abs(kv[1]["change_pct"]), reverse=True
        )[:5]

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

    # ------------------------------------------------------------------
    # Theme tracker
    # ------------------------------------------------------------------

    def _render_theme_tracker(self) -> None:
        """Render the Theme Tracker section with sparklines from macro feature history."""
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

        cards: list[str] = []
        for theme in _THEME_CONFIGS:
            feature = theme["feature"]
            theme_color = theme["color"]
            r, g, b = _hex_to_rgb(theme_color)
            theme_bg = f"rgba({r},{g},{b},0.12)"
            theme_icon = _theme_icon_html(theme["icon"], theme_color)
            value = latest_map.get(feature)

            if value is None:
                cards.append(
                    f"<div class='theme-card' style='--theme-color:{theme_color};--theme-bg:{theme_bg};'>"
                    f"{theme_icon}"
                    f"<div class='theme-name'>{escape(theme['name'])}</div>"
                    "<div class='theme-trend'>No data</div>"
                    "<div class='theme-desc'>Waiting for enough feature history.</div>"
                    "<div class='theme-sparkline-wrap'><div class='theme-sparkline-empty'>No trend</div></div>"
                    "</div>"
                )
                continue

            trend_label, _trend_color = theme["trend_fn"](value)
            description = theme["description_fn"](value)
            sparkline = "<div class='theme-sparkline-empty'>No trend</div>"
            if not matrix.empty and feature in matrix.columns:
                series = matrix[feature].dropna().tail(30)
                if len(series) >= 3:
                    sparkline = _mini_sparkline_svg(series, color=theme_color)

            cards.append(
                f"<div class='theme-card' style='--theme-color:{theme_color};--theme-bg:{theme_bg};'>"
                f"{theme_icon}"
                f"<div class='theme-name'>{escape(theme['name'])}</div>"
                f"<div class='theme-trend'>{escape(trend_label)}</div>"
                f"<div class='theme-desc'>{escape(description)}</div>"
                f"<div class='theme-sparkline-wrap'>{sparkline}</div>"
                "</div>"
            )

        st.markdown(
            "<div class='theme-tracker-band'>"
            "<div class='theme-tracker-head'>"
            "<div class='theme-tracker-title'>Theme Tracker</div>"
            "<span class='theme-info'>i</span>"
            "</div>"
            "<div class='theme-tracker-subtitle'>"
            "Cross-market narratives monitored from news, rates, credit, and macro data."
            "</div>"
            f"<div class='theme-grid'>{''.join(cards)}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Sidebar: news filters
    # ------------------------------------------------------------------

    def _render_news_filters(self, items: list[dict]) -> None:
        """Render sidebar News Filters as same-page buttons with counts and selected state."""
        bucket_counts: dict[str, int] = {}
        for item in items:
            b = item.get("bucket", "macro")
            bucket_counts[b] = bucket_counts.get(b, 0) + 1

        total = len(items)
        active_filters: set[str] = st.session_state.get("news_filter_buckets", set())

        st.markdown(
            "<div class='sidebar-section-header'>News Filters</div>", unsafe_allow_html=True
        )

        filters = [("all", "All News", total)] + [
            (b, _BUCKET_LABELS.get(b, b.title()), bucket_counts.get(b, 0))
            for b in ("rates", "credit", "macro", "etfs", "policy", "inflation")
        ]

        dynamic_css: list[str] = ["<style>"]
        for bucket_key, _display_label, count in filters:
            is_active = (bucket_key == "all" and not active_filters) or (
                bucket_key in active_filters
            )
            color = _BUCKET_COLORS.get(bucket_key, "#687A5D")
            suffix = f"{count} ✓" if is_active else str(count)
            background = (
                _BUCKET_BACKGROUND_COLORS.get(bucket_key, "#EEF1E8") if is_active else "#FBF8F1"
            )
            icon_url = _svg_data_uri(_FILTER_ICON_SVGS[bucket_key].format(color=color))
            active_shadow = (
                f"inset 4px 0 0 {color}, inset 0 0 0 9999px {background}" if is_active else "none"
            )
            dynamic_css.append(
                f".st-key-filter_{bucket_key}{{background:{background} !important;}}"
                f".st-key-filter_{bucket_key} div[data-testid='stButton']{{background:{background} !important;}}"
                f".st-key-filter_{bucket_key} button{{"
                f"background:{background} !important;"
                f"box-shadow:{active_shadow} !important;"
                f"}}"
                f".st-key-filter_{bucket_key} button p{{color:{color} !important;}}"
                f".st-key-filter_{bucket_key} button::before{{"
                f'background-image:url("{icon_url}");'
                f"}}"
                f".st-key-filter_{bucket_key} button::after{{"
                f"content:'{suffix}';color:{color};"
                f"}}"
            )
        dynamic_css.append("</style>")

        st.markdown("".join(dynamic_css), unsafe_allow_html=True)
        for bucket_key, display_label, _count in filters:
            with st.container(key=f"filter_{bucket_key}"):
                if st.button(display_label, key=f"nf_{bucket_key}", use_container_width=True):
                    if bucket_key == "all":
                        st.session_state["news_filter_buckets"] = set()
                    elif bucket_key in active_filters:
                        st.session_state["news_filter_buckets"] = active_filters - {bucket_key}
                    else:
                        st.session_state["news_filter_buckets"] = active_filters | {bucket_key}
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
            "<div class='sidebar-section-header'>Upcoming Events</div>",
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
            "<div class='sidebar-section-header'>News Sources</div>",
            unsafe_allow_html=True,
        )

        source_counts: dict[str, int] = {}
        for item in items:
            src = (item.get("source") or "Unknown").strip()
            source_counts[src] = source_counts.get(src, 0) + 1

        top_sources = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]

        rows = "".join(
            f"<div class='source-row'>"
            f"{_source_logo_html(src)}"
            f"<span class='source-name'>{escape(src)}</span>"
            f"<span class='source-count'>{count}</span>"
            f"</div>"
            for src, count in top_sources
        )
        st.markdown(
            f"<div>{rows}</div>",
            unsafe_allow_html=True,
        )
