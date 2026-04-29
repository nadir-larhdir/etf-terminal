from __future__ import annotations

from services.news.taxonomy import classify_bucket, is_promotional, matches_feed


def test_news_taxonomy_splits_credit_from_fixed_income_etfs() -> None:
    assert classify_bucket("CDX spreads tighten as credit compression extends") == "credit"
    assert classify_bucket("Treasury ETF inflows rise as duration demand grows") == "etfs"
    assert matches_feed("credit", "CDS spread widening hits corporate bonds")
    assert matches_feed("etfs", "Investment grade bond ETF flows accelerate")


def test_news_taxonomy_filters_promotional_headlines() -> None:
    assert is_promotional("Which is the better ETF to buy now?", "Motley Fool")
    assert not is_promotional("Fed officials debate rate cut path", "Reuters")
