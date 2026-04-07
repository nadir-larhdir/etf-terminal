from __future__ import annotations

from fixed_income.config.text_utils import security_text_blob


def classify_bucket(security) -> str:
    asset_class = str(security.asset_class or "")
    text_blob = security_text_blob(security)

    if asset_class == "Inflation-Linked":
        return "Inflation-Linked"
    if asset_class == "Floating Rate":
        return "Floating Rate"
    if asset_class == "MBS":
        return "Mortgage / Securitized"
    if asset_class == "Municipal":
        return "Muni"
    if asset_class == "HY Credit":
        return "High Yield"
    if asset_class == "IG Credit":
        return "Investment Grade Credit"
    if asset_class == "UST Short":
        return "Short Duration / Cash-like"
    if asset_class.startswith("UST "):
        return "Treasury"

    if "tips" in text_blob or "inflation" in text_blob:
        return "Inflation-Linked"
    if any(token in text_blob for token in ("floating rate", "bank loan", "loan participation")):
        return "Floating Rate"
    if any(token in text_blob for token in ("mortgage", "mbs", "securitized")):
        return "Mortgage / Securitized"
    if any(token in text_blob for token in ("preferred", "hybrid")):
        return "Preferred / Hybrid"
    if any(token in text_blob for token in ("municipal", "muni")):
        return "Muni"
    if any(token in text_blob for token in ("high yield", "junk")):
        return "High Yield"
    if any(token in text_blob for token in ("investment grade", "corporate bond", "credit")):
        return "Investment Grade Credit"
    if any(token in text_blob for token in ("cash", "ultra short", "1-3 month", "1-3 year", "short treasury")):
        return "Short Duration / Cash-like"
    if "treasury" in text_blob:
        return "Treasury"
    return "Unknown"


def duration_hint(security) -> str:
    return security_text_blob(security)
