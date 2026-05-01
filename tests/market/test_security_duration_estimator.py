from __future__ import annotations

import fixed_income.analytics.duration_estimator as duration_estimator
import scripts.market.enrich_metadata_from_fmp as enrich_metadata
from fixed_income.analytics.duration_estimator import (
    SecurityDurationEstimator,
    duration_source_details,
    issuer_from_long_name,
)
from services.market.etf import (
    ISHARES_FUNDS,
    ETFAnalytics,
)


class FakeDurationEstimator:
    def get_analytics(self, ticker: str) -> ETFAnalytics | None:
        if ticker != "SLQD":
            return None
        return ETFAnalytics(
            ticker=ticker,
            provider="iShares",
            effective_duration=1.94,
            ytm=4.25,
            oas=72.0,
            convexity=0.31,
            avg_maturity=2.45,
        )

    def estimate_duration(self, ticker: str) -> float | None:
        return {"SLQD": 1.9}.get(ticker)


def test_issuer_from_long_name_uses_first_word() -> None:
    assert (
        issuer_from_long_name("iShares 0-5 Year Investment Grade Corporate Bond ETF") == "iShares"
    )
    assert issuer_from_long_name("Vanguard Short-Term Corporate Bond ETF") == "Vanguard"


def test_duration_estimator_uses_provider_analytics(monkeypatch) -> None:
    class FakeETF:
        def __init__(self, ticker: str, session=None) -> None:
            self.ticker = ticker

        def get_analytics(self) -> ETFAnalytics:
            return ETFAnalytics(
                ticker=self.ticker,
                provider="SPDR",
                effective_duration=4.24,
                modified_duration=4.1,
            )

    monkeypatch.setattr(duration_estimator, "ETF", FakeETF)

    estimator = SecurityDurationEstimator()

    assert estimator.estimate_duration("spab") == 4.2


def test_duration_source_details_returns_provider() -> None:
    assert duration_source_details("LQD") == ("Provider Analytics", "iShares")
    assert duration_source_details("BND") == ("Provider Analytics", "Vanguard")
    assert duration_source_details("SPAB") == ("Provider Analytics", "SPDR")
    assert duration_source_details("PCY") == ("Provider Analytics", "Invesco")


def test_ishares_registry_keeps_known_product_ids() -> None:
    expected_ids = {
        "AGG": "239458",
        "EMB": "239572",
        "FLOT": "239534",
        "GOVT": "239458",
        "HYG": "239565",
        "IEF": "239456",
        "IEI": "239455",
        "IGSB": "239451",
        "IUSB": "264615",
        "LQD": "239566",
        "MBB": "239465",
        "MUB": "239766",
        "SHY": "239452",
        "SHYG": "258100",
        "SLQD": "258098",
        "STIP": "239450",
        "TIP": "239467",
        "TLT": "239454",
    }

    for ticker, product_id in expected_ids.items():
        assert ISHARES_FUNDS[ticker][0] == product_id


def test_build_metadata_row_sets_issuer_from_long_name_and_duration(monkeypatch) -> None:
    monkeypatch.setattr(
        enrich_metadata,
        "get_etf_description",
        lambda ticker: {
            "ticker": ticker,
            "long_name": "iShares 0-5 Year Investment Grade Corporate Bond ETF",
            "description": "Short duration IG credit ETF.",
            "category": "Investment Grade",
            "benchmark_index": None,
            "issuer": "BlackRock",
            "expense_ratio": 0.15,
            "total_assets": 100.0,
            "currency": "USD",
            "exchange": "NASDAQ",
            "quote_type": "etf",
        },
    )

    row = enrich_metadata.build_metadata_row(
        "SLQD",
        existing_row=None,
        duration_estimator=FakeDurationEstimator(),
    )

    assert row["issuer"] == "iShares"
    assert row["duration"] == 1.9
    assert row["yield_to_maturity"] == 4.25
    assert row["oas"] == 72.0
    assert row["years_to_maturity"] == 2.45
    assert row["convexity"] == 0.31


def test_build_metadata_row_uses_internal_category_overrides(monkeypatch) -> None:
    monkeypatch.setattr(
        enrich_metadata,
        "get_etf_description",
        lambda ticker: {
            "ticker": ticker,
            "long_name": f"{ticker} Fixed Income ETF",
            "description": "Fixed income ETF.",
            "category": "Municipal",
            "benchmark_index": None,
            "issuer": "Issuer",
            "expense_ratio": None,
            "total_assets": None,
            "currency": "USD",
            "exchange": "NYSE",
            "quote_type": "etf",
        },
    )

    expected = {
        "BND": ("Core Bond", None),
        "IUSB": ("Core Bond", None),
        "FLRN": ("Floating Rate", None),
        "STIP": ("Inflation-Linked", None),
        "TIP": ("Inflation-Linked", None),
        "EDV": ("UST Long", "Treasury STRIPS"),
    }

    for ticker, (category, duration_bucket) in expected.items():
        row = enrich_metadata.build_metadata_row(
            ticker,
            existing_row={"category": "Municipal", "duration_bucket": "Long Duration"},
        )

        assert row["category"] == category
        if duration_bucket is not None:
            assert row["duration_bucket"] == duration_bucket


def test_build_metadata_row_prefers_config_category_over_existing_and_fmp(monkeypatch) -> None:
    monkeypatch.setattr(
        enrich_metadata,
        "get_etf_description",
        lambda ticker: {
            "ticker": ticker,
            "long_name": "SPDR Portfolio Long Term Treasury ETF",
            "description": "Long term Treasury ETF.",
            "category": "UST Short",
            "benchmark_index": None,
            "issuer": "State Street",
            "expense_ratio": None,
            "total_assets": None,
            "currency": "USD",
            "exchange": "NYSE",
            "quote_type": "etf",
        },
    )

    row = enrich_metadata.build_metadata_row(
        "SPTL",
        existing_row={"category": "UST Short", "duration_bucket": "Long Duration"},
    )

    assert row["category"] == "UST Long"
