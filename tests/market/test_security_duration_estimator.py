from __future__ import annotations

import scripts.market.enrich_metadata_from_fmp as enrich_metadata
from services.market.duration_estimator import SecurityDurationEstimator, issuer_from_long_name


class StubDurationEstimator(SecurityDurationEstimator):
    def __init__(self) -> None:
        self.engine = None
        self._duration_cache = {}

    def _fetch_ishares_duration(self, ticker: str) -> float | None:
        return {
            "HYG": 2.9,
            "SLQD": 1.9,
        }.get(ticker)

    def _log_return_beta(self, left_ticker: str, right_ticker: str) -> float | None:
        return {
            ("JNK", "HYG"): 1.1,
            ("SPSB", "SLQD"): 0.8,
        }.get((left_ticker, right_ticker))

    def _estimate_curve_duration(self, ticker: str) -> float | None:
        return {
            "HYD": 5.2,
        }.get(ticker)


class FakeDurationEstimator:
    def estimate_duration(self, ticker: str) -> float | None:
        return {"SLQD": 1.9}.get(ticker)


def test_issuer_from_long_name_uses_first_word() -> None:
    assert (
        issuer_from_long_name("iShares 0-5 Year Investment Grade Corporate Bond ETF") == "iShares"
    )
    assert issuer_from_long_name("Vanguard Short-Term Corporate Bond ETF") == "Vanguard"


def test_duration_estimator_prefers_ishares_then_proxy_then_curve() -> None:
    estimator = StubDurationEstimator()

    assert estimator.estimate_duration("HYG") == 2.9
    assert estimator.estimate_duration("JNK") == 3.2
    assert estimator.estimate_duration("SPSB") == 1.5
    assert estimator.estimate_duration("HYD") == 5.2


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
        "HYD": ("HY Credit", None),
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
