"""News page — Bloomberg-style market brief for the fixed income ETF terminal."""

from __future__ import annotations

import base64
import re
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config import FMP_API_KEY, FMP_BASE_URL
from dashboard.cache import (
    app_cache_key,
    cached_feature_matrix,
    cached_latest_feature_values,
)
from dashboard.perf import timed_block
from dashboard.render import stylesheet
from services.market.fmp_client import FMPClient
from services.news import NewsFeedService, classify_bucket

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
            ("Trending", "#8AA05A")
            if v < -0.1
            else ("Mixed", "#C97C6B") if abs(v) < 0.1 else ("Hawkish", "#B46A5A")
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
            ("Improving", "#8AA05A")
            if v < -2
            else ("Stable", "#707A68") if abs(v) < 2 else ("Widening", "#C97C6B")
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
            ("Easing", "#8AA05A")
            if v < -0.05
            else ("Mixed", "#707A68") if abs(v) < 0.05 else ("Rising", "#C97C6B")
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
            ("Inverted", "#C97C6B")
            if v < 0
            else ("Flat", "#707A68") if v < 0.5 else ("Steepening", "#8AA05A")
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
            ("Restrictive", "#C97C6B")
            if v < 0
            else ("Neutral", "#707A68") if v < 0.5 else ("Accommodative", "#8AA05A")
        ),
    },
]

_EASTERN_TZ = ZoneInfo("America/New_York")
_ECONOMIC_CALENDAR_CACHE_VERSION = "v2"
_ECONOMIC_CALENDAR_LOOKAHEAD_DAYS = 14
_EVENT_KEYWORDS = (
    "auction",
    "beige book",
    "cpi",
    "consumer confidence",
    "durable goods",
    "ecb",
    "fed",
    "fomc",
    "gdp",
    "home sales",
    "housing starts",
    "initial jobless",
    "ism",
    "jolts",
    "manufacturing",
    "nonfarm",
    "payroll",
    "pce",
    "pmi",
    "ppi",
    "rate decision",
    "retail sales",
    "treasury",
    "unemployment",
)
_EVENT_IMPORTANCE_VALUES = {"high", "medium", "3", "2"}

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


@st.cache_data(ttl=3600, show_spinner=False)
def _load_upcoming_events(
    cache_key: str,
    api_key: str,
    cache_version: str = _ECONOMIC_CALENDAR_CACHE_VERSION,
) -> tuple[list[dict[str, str]], str | None]:
    """Fetch upcoming macro events from FMP's economic calendar."""
    del cache_version
    if not api_key:
        return [], "Set FMP_API_KEY to load the live economic calendar."

    start_date = datetime.now(_EASTERN_TZ).date()
    end_date = start_date + timedelta(days=_ECONOMIC_CALENDAR_LOOKAHEAD_DAYS)
    try:
        rows = FMPClient(api_key=api_key, base_url=FMP_BASE_URL).get_economic_calendar(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
        )
    except Exception as exc:  # noqa: BLE001
        return [], f"Economic calendar unavailable: {exc}"

    now = datetime.now(_EASTERN_TZ)
    events = _normalise_upcoming_events(rows, now=now)
    if not events:
        events = _normalise_upcoming_events(rows, now=now, require_relevance=False)
    return events[:5], None


# ---------------------------------------------------------------------------
# Internal helpers (module-level, pure functions)
# ---------------------------------------------------------------------------


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


def _published_timestamp(item: dict) -> float:
    """Return a sortable timestamp for a news item, with undated items last."""
    published_at = item.get("published_at")
    if not published_at:
        return float("-inf")
    try:
        dt = datetime.fromisoformat(str(published_at))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except (ValueError, TypeError, OSError):
        return float("-inf")


def _dedupe_items(feed_data: dict[str, Any]) -> list[dict]:
    """Flatten all feed buckets into a single deduplicated list, newest first."""
    items_by_key: dict[str, dict] = {}
    for bucket in ("rates", "credit", "etfs", "macro"):
        for item in feed_data.get(bucket, {}).get("items", []):
            key = re.sub(r"\s+", " ", item.get("title", "")).strip().lower()
            if not key:
                continue
            bucket_name = item.get("bucket") or classify_bucket(item.get("title", ""))
            normalized = {**item, "bucket": bucket_name}
            existing = items_by_key.get(key)
            if existing is None or _published_timestamp(normalized) > _published_timestamp(
                existing
            ):
                items_by_key[key] = normalized
    return sorted(items_by_key.values(), key=_published_timestamp, reverse=True)


def _calendar_field(row: dict, *keys: str) -> str:
    """Return the first non-empty calendar field as a string."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_event_datetime(row: dict) -> datetime | None:
    """Parse an FMP calendar row date/time into Eastern time."""
    raw = _calendar_field(row, "date", "datetime", "time")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = pd.to_datetime(raw, errors="raise").to_pydatetime()
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_EASTERN_TZ)
    return dt.astimezone(_EASTERN_TZ)


def _event_day_label(event_dt: datetime, today) -> str:
    """Return Today/Tomorrow or compact month-day label for an event."""
    event_date = event_dt.date()
    if event_date == today:
        return "Today"
    if event_date == today + timedelta(days=1):
        return "Tomorrow"
    return f"{event_dt.strftime('%b')} {event_dt.day}"


def _is_us_event(row: dict) -> bool:
    """Return True for US/USD economic calendar rows."""
    country = _calendar_field(row, "country").lower()
    currency = _calendar_field(row, "currency").upper()
    return currency == "USD" or country in {
        "us",
        "usa",
        "united states",
        "united states of america",
    }


def _is_relevant_event(row: dict) -> bool:
    """Return True for market-moving rates, inflation, policy, and growth events."""
    event_name = _calendar_field(row, "event", "name", "title")
    if not event_name:
        return False

    importance = _calendar_field(row, "importance", "impact").lower()
    has_keyword = any(keyword in event_name.lower() for keyword in _EVENT_KEYWORDS)
    return has_keyword or importance in _EVENT_IMPORTANCE_VALUES


def _normalise_upcoming_events(
    rows: list[dict],
    *,
    now: datetime,
    require_relevance: bool = True,
) -> list[dict[str, str]]:
    """Convert raw FMP calendar rows into sidebar-ready event dicts."""
    events: list[dict[str, str]] = []
    today = now.date()
    for row in rows:
        event_dt = _parse_event_datetime(row)
        if event_dt is None or event_dt < now:
            continue
        if not _is_us_event(row):
            continue
        if require_relevance and not _is_relevant_event(row):
            continue

        name = _calendar_field(row, "event", "name", "title")
        time_label = (
            "TBA" if event_dt.hour == 0 and event_dt.minute == 0 else event_dt.strftime("%H:%M ET")
        )
        events.append(
            {
                "time": time_label,
                "name": name,
                "day": _event_day_label(event_dt, today),
                "sort_key": event_dt.isoformat(),
            }
        )

    return sorted(events, key=lambda event: event["sort_key"])


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
            # The weights already carry the direction: a negative weight means a higher
            # reading is worse for bonds, so the raw value is applied as-is.
            score += float(row["value"]) * weight
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
        st.markdown(stylesheet("news_page.css"), unsafe_allow_html=True)

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

        label_color = "#6FAF72" if score > 0.15 else "#C97C6B" if score < -0.15 else "#707A68"

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
        """Render the Upcoming Events list from the live economic calendar."""
        st.markdown(
            "<div class='sidebar-section-header'>Upcoming Events</div>",
            unsafe_allow_html=True,
        )

        cache_key = app_cache_key(self.macro_feature_store.engine)
        events, calendar_error = _load_upcoming_events(
            cache_key,
            FMP_API_KEY,
            _ECONOMIC_CALENDAR_CACHE_VERSION,
        )
        if calendar_error:
            rows = (
                "<div class='event-row'>"
                "<span class='event-time'>Live</span>"
                f"<span class='event-name'>{escape(calendar_error)}</span>"
                "<span class='event-day'>--</span>"
                "</div>"
            )
        elif not events:
            rows = (
                "<div class='event-row'>"
                "<span class='event-time'>Next</span>"
                "<span class='event-name'>No major US macro events found</span>"
                "<span class='event-day'>14d</span>"
                "</div>"
            )
        else:
            rows = "".join(
                f"<div class='event-row'>"
                f"<span class='event-time'>{escape(ev['time'])}</span>"
                f"<span class='event-name'>{escape(ev['name'])}</span>"
                f"<span class='event-day'>{escape(ev['day'])}</span>"
                f"</div>"
                for ev in events
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
