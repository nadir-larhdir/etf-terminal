"""Text helpers for building searchable blobs from ETF attributes."""

from __future__ import annotations


def etf_text_blob(etf) -> str:
    """Return a single lowercase string concatenating all text fields of an ETF.

    Used by bucket classifiers and proxy selectors to match keywords without
    requiring a strict enum on every attribute.
    """
    return " ".join(
        str(value or "")
        for value in (
            etf.ticker,
            etf.name,
            etf.asset_class,
            etf.metadata.get("category"),
            etf.metadata.get("long_name"),
            etf.metadata.get("description"),
            etf.metadata.get("duration_bucket"),
        )
    ).lower()
