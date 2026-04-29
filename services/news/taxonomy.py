"""Shared news headline taxonomy for feed filtering and dashboard buckets."""

from __future__ import annotations

PROMOTIONAL_PATTERNS = (
    "which is the better",
    "which is better",
    "the best ones",
    "best ",
    "top ",
    "should you buy",
    "buy now",
    "investors are flocking",
    "why this etf",
    "why this stock",
    "motley fool",
)

FIXED_INCOME_ETF_TERMS = (
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

BUCKET_KEYWORDS = {
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
    "rates": (
        "treasury",
        "yield",
        "yields",
        "curve",
        "bond market",
        "duration",
        "auction",
        "rates",
        "fed",
        "fomc",
    ),
    "credit": (
        "credit",
        "spread",
        "spreads",
        "spread compression",
        "spread widening",
        "spread tightening",
        "compression",
        "widening",
        "tightening",
        "investment grade",
        "high yield",
        "leveraged loan",
        "default swap",
        "cds",
        "cdx",
        "oas",
        "junk bond",
        "corporate bond",
    ),
    "macro": (
        "gdp",
        "payroll",
        "payrolls",
        "unemployment",
        "labor",
        "retail sales",
        "economy",
        "economic",
        "china",
        "trade",
        "macro",
    ),
}

FEED_BUCKET_ALIASES = {
    "macro": {"macro", "policy", "inflation"},
}


def classify_bucket(title: str) -> str:
    """Classify a headline into the most specific news bucket."""
    lower = title.casefold()
    if "etf" in lower and any(term in lower for term in FIXED_INCOME_ETF_TERMS):
        return "etfs"
    for bucket, keywords in BUCKET_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return bucket
    return "macro"


def is_promotional(title: str, source: str = "") -> bool:
    """Return True for low-signal promotional or stock-picking headlines."""
    combined = f"{title} {source}".casefold()
    return any(pattern in combined for pattern in PROMOTIONAL_PATTERNS)


def matches_feed(feed_key: str, title: str) -> bool:
    """Return True when a classified headline belongs in a configured feed."""
    bucket = classify_bucket(title)
    allowed = FEED_BUCKET_ALIASES.get(feed_key, {feed_key})
    return bucket in allowed
