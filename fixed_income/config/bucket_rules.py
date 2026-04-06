from __future__ import annotations


def classify_bucket(security) -> str:
    text_blob = " ".join(
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

    if "tips" in text_blob or "inflation" in text_blob or security.asset_class == "Inflation-Linked":
        return "Inflation-Linked"
    if any(token in text_blob for token in ("floating rate", "bank loan", "loan participation")) or security.asset_class == "Floating Rate":
        return "Floating Rate"
    if any(token in text_blob for token in ("mortgage", "mbs", "securitized")) or security.asset_class == "MBS":
        return "Mortgage / Securitized"
    if any(token in text_blob for token in ("preferred", "hybrid")):
        return "Preferred / Hybrid"
    if any(token in text_blob for token in ("municipal", "muni")) or security.asset_class == "Municipal":
        return "Muni"
    if any(token in text_blob for token in ("high yield", "junk")) or security.asset_class == "HY Credit":
        return "High Yield"
    if any(token in text_blob for token in ("investment grade", "corporate bond", "credit")) or security.asset_class == "IG Credit":
        return "Investment Grade Credit"
    if any(token in text_blob for token in ("cash", "ultra short", "1-3 month", "1-3 year", "short treasury")) or security.asset_class == "UST Short":
        return "Short Duration / Cash-like"
    if "treasury" in text_blob or str(security.asset_class or "").startswith("UST "):
        return "Treasury"
    return "Unknown"


def duration_hint(security) -> str:
    return " ".join(
        str(value or "")
        for value in (
            security.metadata.get("duration_bucket"),
            security.name,
            security.metadata.get("long_name"),
            security.metadata.get("description"),
        )
    ).lower()
