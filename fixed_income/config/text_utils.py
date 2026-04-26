"""Text helpers for building searchable blobs from security attributes."""

from __future__ import annotations


def security_text_blob(security) -> str:
    """Return a single lowercase string concatenating all text fields of a security.

    Used by bucket classifiers and proxy selectors to match keywords without
    requiring a strict enum on every attribute.
    """
    return " ".join(
        str(value or "")
        for value in (
            security.ticker,
            security.name,
            security.asset_class,
            security.metadata.get("category"),
            security.metadata.get("long_name"),
            security.metadata.get("description"),
            security.metadata.get("duration_bucket"),
        )
    ).lower()
