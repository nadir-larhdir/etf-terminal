"""Asset-bucket classification, spread-proxy selection, and their display labels."""

from __future__ import annotations

import pytest

from config.asset_classes import normalize_asset_class
from fixed_income.analytics.presenters import format_oas_proxy_label
from fixed_income.analytics.risk_proxy_selector import RiskProxySelector
from fixed_income.config.bucket_rules import classify_bucket, duration_hint
from fixed_income.config.spread_proxy_rules import spread_proxy_for_bucket
from fixed_income.config.text_utils import etf_text_blob
from fixed_income.etfs import ETF


def _etf(ticker: str = "TEST", *, asset_class: str | None = None, **metadata: str) -> ETF:
    return ETF(ticker, name=metadata.pop("name", None), asset_class=asset_class, metadata=metadata)


# ── asset-class normalisation ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CREDIT IG", "IG Credit"),
        ("ig credit", "IG Credit"),
        ("CREDIT HY", "HY Credit"),
        ("INFLATION", "Inflation-Linked"),
        ("inflation linked", "Inflation-Linked"),
        ("Inflation-Linked", "Inflation-Linked"),
    ],
)
def test_known_aliases_map_to_the_canonical_label(raw: str, expected: str) -> None:
    assert normalize_asset_class(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_a_missing_asset_class_becomes_other(raw: str | None) -> None:
    assert normalize_asset_class(raw) == "Other"


def test_an_unrecognised_label_is_passed_through_trimmed() -> None:
    assert normalize_asset_class("  Sovereign  ") == "Sovereign"


# ── bucket classification ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("asset_class", "bucket"),
    [
        ("Inflation-Linked", "Inflation-Linked"),
        ("Floating Rate", "Floating Rate"),
        ("MBS", "Mortgage / Securitized"),
        ("Municipal", "Muni"),
        ("HY Credit", "High Yield"),
        ("IG Credit", "Investment Grade Credit"),
        ("UST Short", "Short Duration / Cash-like"),
    ],
)
def test_a_structured_asset_class_decides_the_bucket(asset_class: str, bucket: str) -> None:
    assert classify_bucket(_etf(asset_class=asset_class)) == bucket


@pytest.mark.parametrize("asset_class", ["UST Belly", "UST Long", "UST Broad"])
def test_any_other_treasury_class_buckets_as_treasury(asset_class: str) -> None:
    assert classify_bucket(_etf(asset_class=asset_class)) == "Treasury"


def test_a_structured_class_wins_over_conflicting_keywords() -> None:
    etf = _etf(asset_class="MBS", description="high yield corporate credit")

    assert classify_bucket(etf) == "Mortgage / Securitized"


@pytest.mark.parametrize(
    ("text", "bucket"),
    [
        ("TIPS bond fund", "Inflation-Linked"),
        ("senior bank loan fund", "Floating Rate"),
        ("agency mbs portfolio", "Mortgage / Securitized"),
        ("preferred securities", "Preferred / Hybrid"),
        ("municipal bond index", "Muni"),
        ("high yield corporate", "High Yield"),
        ("investment grade corporate", "Investment Grade Credit"),
        ("ultra short government", "Short Duration / Cash-like"),
        ("long treasury index", "Treasury"),
    ],
)
def test_keywords_classify_an_etf_with_no_structured_class(text: str, bucket: str) -> None:
    assert classify_bucket(_etf(description=text)) == bucket


def test_an_unclassifiable_etf_is_reported_as_unknown() -> None:
    assert classify_bucket(_etf(description="equity index fund")) == "Unknown"


def test_keyword_matching_is_case_insensitive() -> None:
    assert classify_bucket(_etf(description="HIGH YIELD CORPORATE")) == "High Yield"


def test_the_text_blob_pulls_from_every_descriptive_field() -> None:
    etf = ETF(
        "LQD",
        name="iShares IG",
        asset_class="IG Credit",
        metadata={"category": "Corporate", "description": "Bonds", "duration_bucket": "Belly"},
    )

    blob = etf_text_blob(etf)

    for fragment in ("lqd", "ishares ig", "corporate", "bonds", "belly"):
        assert fragment in blob


def test_the_text_blob_tolerates_missing_fields() -> None:
    assert etf_text_blob(ETF("LQD")).split() == ["lqd"]


def test_the_duration_hint_is_the_text_blob() -> None:
    etf = _etf(description="long treasury")

    assert duration_hint(etf) == etf_text_blob(etf)


# ── spread proxy selection ──────────────────────────────────────────────────


def test_investment_grade_defaults_to_the_broad_ig_index() -> None:
    assert spread_proxy_for_bucket("Investment Grade Credit", _etf()) == "BAMLC0A0CM"


def test_a_bbb_fund_uses_the_bbb_index() -> None:
    etf = _etf(description="BBB rated corporate bonds")

    assert spread_proxy_for_bucket("Investment Grade Credit", etf) == "BAMLC0A4CBBB"


def test_high_yield_defaults_to_the_broad_hy_index() -> None:
    assert spread_proxy_for_bucket("High Yield", _etf()) == "BAMLH0A0HYM2"


@pytest.mark.parametrize("text", ["single-b rated", "single b rated"])
def test_a_single_b_fund_uses_the_single_b_index(text: str) -> None:
    assert spread_proxy_for_bucket("High Yield", _etf(description=text)) == "BAMLH0A2HYB"


@pytest.mark.parametrize("bucket", ["Treasury", "Muni", "Inflation-Linked", "Unknown"])
def test_buckets_with_no_credit_risk_have_no_spread_proxy(bucket: str) -> None:
    assert spread_proxy_for_bucket(bucket, _etf()) is None


def test_the_selector_reports_both_the_bucket_and_its_proxy() -> None:
    selection = RiskProxySelector().select_for_etf(_etf(asset_class="IG Credit"))

    assert selection.asset_bucket == "Investment Grade Credit"
    assert selection.spread_proxy_series_id == "BAMLC0A0CM"


def test_the_selection_round_trips_to_a_dict() -> None:
    selection = RiskProxySelector().select_for_etf(_etf(asset_class="HY Credit"))

    assert selection.to_dict() == {
        "asset_bucket": "High Yield",
        "spread_proxy_series_id": "BAMLH0A0HYM2",
    }


# ── proxy labels ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("series_id", "label"),
    [
        ("BAMLC0A0CM", "BoFA IG OAS"),
        ("BAMLC0A4CBBB", "BoFA BBB OAS"),
        ("BAMLH0A0HYM2", "BoFA HY OAS"),
        ("BAMLH0A2HYB", "BoFA Single-B OAS"),
    ],
)
def test_each_known_proxy_has_a_readable_label(series_id: str, label: str) -> None:
    assert format_oas_proxy_label(series_id) == label


def test_an_unknown_proxy_falls_back_to_its_raw_id() -> None:
    assert format_oas_proxy_label("NEWSERIES") == "NEWSERIES"


def test_a_missing_proxy_reads_as_not_applicable() -> None:
    assert format_oas_proxy_label(None) == "N/A"
