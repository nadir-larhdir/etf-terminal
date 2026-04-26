"""Label helpers for presenting analytics data in the dashboard."""

from __future__ import annotations

# Human-readable labels for the OAS proxy FRED series shown in the UI.
OAS_PROXY_LABELS = {
    "BAMLC0A0CM": "BoFA IG OAS",
    "BAMLC0A4CBBB": "BoFA BBB OAS",
    "BAMLH0A0HYM2": "BoFA HY OAS",
    "BAMLH0A2HYB": "BoFA Single-B OAS",
}


def format_oas_proxy_label(series_id: str | None) -> str:
    """Return a display-friendly label for an OAS proxy series ID, falling back to the raw ID."""
    return OAS_PROXY_LABELS.get(str(series_id), series_id or "N/A")
