from __future__ import annotations

import requests

from fixed_income.etfs.provider_analytics import (
    ETFAnalytics,
    ETFAnalyticsClient,
    provider_for_ticker,
)


def issuer_from_long_name(long_name: str | None) -> str | None:
    if not long_name:
        return None
    tokens = str(long_name).strip().split()
    return tokens[0] if tokens else None


def duration_source_details(ticker: str) -> tuple[str, str]:
    provider = provider_for_ticker(ticker)
    if not provider:
        return ("Provider", "Unavailable")
    return ("PCF", provider)


class ETFDurationEstimator:
    def __init__(self, engine=None, session: requests.Session | None = None):
        self.engine = engine
        self.session = session or requests.Session()
        self._analytics_cache: dict[str, ETFAnalytics] = {}

    def get_analytics(self, ticker: str) -> ETFAnalytics | None:
        normalized = str(ticker).strip().upper()
        if not normalized:
            return None
        if normalized not in self._analytics_cache:
            self._analytics_cache[normalized] = ETFAnalyticsClient(
                normalized, session=self.session
            ).get_analytics()
        return self._analytics_cache[normalized]

    def estimate_duration(self, ticker: str) -> float | None:
        analytics = self.get_analytics(ticker)
        if analytics is None:
            return None
        value = analytics.preferred_duration
        return round(float(value), 1) if value is not None else None
