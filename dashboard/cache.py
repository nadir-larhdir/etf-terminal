from __future__ import annotations

import pandas as pd
import streamlit as st

from db.sql import cache_scope
from fixed_income.analytics import is_snapshot_stale, snapshot_age_hours
from fixed_income.analytics.result_models import SecurityAnalyticsSnapshot
from fixed_income.instruments.security import Security


def app_cache_key(engine) -> str:
    return cache_scope(engine)


@st.cache_data(ttl=900, show_spinner=False)
def cached_active_securities(cache_key: str, _security_store) -> pd.DataFrame:
    return _security_store.list_active_securities().copy()


@st.cache_data(ttl=900, show_spinner=False)
def cached_security_metadata(cache_key: str, ticker: str, _metadata_store):
    return _metadata_store.get_ticker_metadata(ticker)


@st.cache_data(ttl=900, show_spinner=False)
def cached_price_history(cache_key: str, ticker: str, start_date, end_date, _price_store) -> pd.DataFrame:
    return _price_store.get_ticker_price_history(ticker, start_date=start_date, end_date=end_date).copy()


@st.cache_data(ttl=900, show_spinner=False)
def cached_multi_price_history(cache_key: str, tickers: tuple[str, ...], start_date, end_date, _price_store):
    return _price_store.get_multi_ticker_price_history(list(tickers), start_date=start_date, end_date=end_date)


@st.cache_data(ttl=900, show_spinner=False)
def cached_feature_matrix(cache_key: str, feature_names: tuple[str, ...], start_date, end_date, _macro_feature_store) -> pd.DataFrame:
    return _macro_feature_store.get_feature_matrix(list(feature_names), start_date=start_date, end_date=end_date).copy()


@st.cache_data(ttl=900, show_spinner=False)
def cached_latest_feature_values(cache_key: str, feature_names: tuple[str, ...], _macro_feature_store) -> pd.DataFrame:
    return _macro_feature_store.get_latest_feature_values(list(feature_names)).copy()


@st.cache_data(show_spinner=False)
def cached_precomputed_analytics_snapshot(
    cache_key: str,
    ticker: str,
    price_as_of: str,
    metadata_duration: float | None,
    _analytics_service,
):
    snapshot = _analytics_service.get_latest_snapshot(ticker)
    return None if snapshot is None else snapshot.to_record()


@st.cache_data(show_spinner=False)
def cached_live_analytics_snapshot(
    cache_key: str,
    ticker: str,
    price_as_of: str,
    macro_as_of: str | None,
    settings_key: str,
    metadata_duration: float | None,
    history: pd.DataFrame,
    metadata: dict,
    asset_class: str | None,
    name: str | None,
    _analytics_service,
):
    security = Security(ticker=ticker, name=name, asset_class=asset_class, metadata=metadata or {}, history=history.copy())
    factor_bundle = _analytics_service.load_factor_bundle(security)
    snapshot = _analytics_service.analyze_factor_bundle(security, factor_bundle)
    return snapshot.to_record()


def restore_analytics_snapshot(record: dict | None) -> SecurityAnalyticsSnapshot | None:
    return None if record is None else SecurityAnalyticsSnapshot.from_record(record)


__all__ = [
    "app_cache_key",
    "cached_active_securities",
    "cached_security_metadata",
    "cached_price_history",
    "cached_multi_price_history",
    "cached_feature_matrix",
    "cached_latest_feature_values",
    "cached_precomputed_analytics_snapshot",
    "cached_live_analytics_snapshot",
    "restore_analytics_snapshot",
    "is_snapshot_stale",
    "snapshot_age_hours",
]
