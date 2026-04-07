from __future__ import annotations

import pandas as pd


def _naive_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize(None) if ts.tzinfo is not None else ts


def snapshot_age_hours(snapshot, now=None) -> float | None:
    if snapshot is None:
        return None
    reference = getattr(snapshot, "updated_at", None) or getattr(snapshot, "as_of_date", None)
    if not reference:
        return None
    current_time = _naive_timestamp(pd.Timestamp.utcnow() if now is None else now)
    reference_time = _naive_timestamp(reference)
    return max((current_time - reference_time).total_seconds() / 3600.0, 0.0)


def is_snapshot_stale(snapshot, now=None, ttl_hours: int = 24, required_as_of_date: str | None = None) -> bool:
    if snapshot is None:
        return True
    if required_as_of_date is not None and str(getattr(snapshot, "as_of_date", None) or "") != str(required_as_of_date):
        return True
    age = snapshot_age_hours(snapshot, now=now)
    if age is None:
        return True
    return age > float(ttl_hours)
