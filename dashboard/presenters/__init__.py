"""Presenters turn store data into the plain view models the templates render.

They hold no Streamlit or HTML, so every number and label on a page can be asserted
directly in a unit test.
"""

from dashboard.presenters.home import (
    DirectionBadge,
    HomePresenter,
    PulseRow,
    RegimeCard,
    SnapshotTile,
    StatCard,
)
from dashboard.presenters.security import PriceCard, metadata_rows

__all__ = [
    "DirectionBadge",
    "HomePresenter",
    "PriceCard",
    "PulseRow",
    "RegimeCard",
    "SnapshotTile",
    "StatCard",
    "metadata_rows",
]
