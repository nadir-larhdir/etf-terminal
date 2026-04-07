from __future__ import annotations


def security_text_blob(security) -> str:
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
