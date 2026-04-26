"""Utilities for determining whether an analytics snapshot is fresh or stale."""

from __future__ import annotations

import pandas as pd


def _naive_timestamp(value) -> pd.Timestamp:
    """Parse a value into a timezone-naive Timestamp for safe arithmetic."""
    ts = pd.Timestamp(value)
    return ts.tz_localize(None) if ts.tzinfo is not None else ts


def snapshot_age_hours(snapshot, now=None) -> float | None:
    """Return the age of a snapshot in hours, measured from updated_at or as_of_date.

    Returns None if the snapshot is None or carries no reference timestamp.
    """
    if snapshot is None:
        return None
    reference = getattr(snapshot, "updated_at", None) or getattr(snapshot, "as_of_date", None)
    if not reference:
        return None
    current = _naive_timestamp(pd.Timestamp.utcnow() if now is None else now)
    ref = _naive_timestamp(reference)
    return max((current - ref).total_seconds() / 3600.0, 0.0)


def is_snapshot_stale(
    snapshot,
    now=None,
    ttl_hours: int = 24,
    required_as_of_date: str | None = None,
    required_estimated_duration: float | None = None,
) -> bool:
    """Return True when the snapshot should be recomputed.

    A snapshot is stale if it is None, older than ttl_hours, has a different
    as_of_date than required, or its duration deviates from required_estimated_duration.
    """
    if snapshot is None:
        return True
    if required_as_of_date is not None:
        if str(getattr(snapshot, "as_of_date", None) or "") != str(required_as_of_date):
            return True
    if required_estimated_duration is not None:
        snap_dur = getattr(snapshot, "estimated_duration", None)
        if snap_dur is None or abs(float(snap_dur) - float(required_estimated_duration)) > 1e-9:
            return True
    age = snapshot_age_hours(snapshot, now=now)
    return age is None or age > float(ttl_hours)
