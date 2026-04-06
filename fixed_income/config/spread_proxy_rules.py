from __future__ import annotations


def spread_proxy_for_bucket(bucket: str, security) -> str | None:
    text_blob = " ".join(
        str(value or "")
        for value in (
            security.ticker,
            security.name,
            security.asset_class,
            security.metadata.get("category"),
            security.metadata.get("long_name"),
            security.metadata.get("description"),
        )
    ).lower()
    if bucket == "Investment Grade Credit":
        return "BAMLC0A4CBBB" if "bbb" in text_blob else "BAMLC0A0CM"
    if bucket == "High Yield":
        return "BAMLH0A2HYB" if "single-b" in text_blob or "single b" in text_blob else "BAMLH0A0HYM2"
    return None
