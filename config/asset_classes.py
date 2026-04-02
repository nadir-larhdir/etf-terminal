"""Canonical asset-class labels used across the app and database."""

ASSET_CLASS_ALIASES = {
    "CREDIT IG": "IG Credit",
    "IG CREDIT": "IG Credit",
    "CREDIT HY": "HY Credit",
    "HY CREDIT": "HY Credit",
    "INFLATION": "Inflation-Linked",
    "INFLATION LINKED": "Inflation-Linked",
    "INFLATION-LINKED": "Inflation-Linked",
}


def normalize_asset_class(asset_class: str | None) -> str:
    """Return the canonical asset-class label for display and persistence."""

    if asset_class is None:
        return "Other"

    normalized = str(asset_class).strip()
    if not normalized:
        return "Other"

    return ASSET_CLASS_ALIASES.get(normalized.upper(), normalized)
