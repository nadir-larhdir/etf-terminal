"""Rules for classifying an ETF into a fixed-income asset bucket."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fixed_income.config.text_utils import etf_text_blob

if TYPE_CHECKING:
    from fixed_income.etfs import ETF


def classify_bucket(etf: ETF) -> str:
    """Return the canonical asset bucket for an ETF.

    Checks the structured asset_class field first, then falls back to keyword
    matching against the combined text blob of all metadata fields.
    """
    asset_class = str(etf.asset_class or "")
    text_blob = etf_text_blob(etf)

    # Structured asset_class overrides take priority over keyword matching.
    _ASSET_CLASS_MAP = {
        "Inflation-Linked": "Inflation-Linked",
        "Floating Rate": "Floating Rate",
        "MBS": "Mortgage / Securitized",
        "Municipal": "Muni",
        "HY Credit": "High Yield",
        "IG Credit": "Investment Grade Credit",
        "UST Short": "Short Duration / Cash-like",
    }
    if asset_class in _ASSET_CLASS_MAP:
        return _ASSET_CLASS_MAP[asset_class]
    if asset_class.startswith("UST "):
        return "Treasury"

    # Keyword fallback on the combined text blob.
    _KEYWORD_MAP = (
        (("tips", "inflation"), "Inflation-Linked"),
        (("floating rate", "bank loan", "loan participation"), "Floating Rate"),
        (("mortgage", "mbs", "securitized"), "Mortgage / Securitized"),
        (("preferred", "hybrid"), "Preferred / Hybrid"),
        (("municipal", "muni"), "Muni"),
        (("high yield", "junk"), "High Yield"),
        (("investment grade", "corporate bond", "credit"), "Investment Grade Credit"),
        (
            ("cash", "ultra short", "1-3 month", "1-3 year", "short treasury"),
            "Short Duration / Cash-like",
        ),
        (("treasury",), "Treasury"),
    )
    for keywords, bucket in _KEYWORD_MAP:
        if any(kw in text_blob for kw in keywords):
            return bucket

    return "Unknown"


def duration_hint(etf: ETF) -> str:
    """Return the full text blob for an ETF, used as a duration classification hint."""
    return etf_text_blob(etf)
