"""Parsing helpers that normalise provider holdings files into store-ready rows."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fixed_income.etfs.holdings import (
    _ishares_csv_header_row,
    _ishares_fund_document_params,
    _mbs_date,
    _normalize_cusip,
    _to_date,
    _to_num,
)

# ── numeric and date coercion ───────────────────────────────────────────────


def test_numeric_strings_are_coerced() -> None:
    assert _to_num(pd.Series(["1.5", "2"])).tolist() == [1.5, 2.0]


def test_unparseable_numbers_become_nan_rather_than_raising() -> None:
    assert _to_num(pd.Series(["1.5", "n/a", "-"])).isna().tolist() == [False, True, True]


def test_dates_are_coerced_and_bad_values_become_nat() -> None:
    result = _to_date(pd.Series(["2030-06-30", "not-a-date"]))

    assert result.iloc[0] == pd.Timestamp("2030-06-30")
    assert pd.isna(result.iloc[1])


# ── CUSIP normalisation ─────────────────────────────────────────────────────


def test_a_nine_character_cusip_is_kept_as_is() -> None:
    assert _normalize_cusip("912828YS3") == "912828YS3"


def test_a_twelve_character_isin_is_trimmed_to_its_cusip() -> None:
    assert _normalize_cusip("US912828YS31") == "912828YS3"


@pytest.mark.parametrize("value", [None, "", "   ", "-", np.nan])
def test_placeholder_identifiers_become_none(value: object) -> None:
    assert _normalize_cusip(value) is None


def test_surrounding_whitespace_is_stripped() -> None:
    assert _normalize_cusip("  912828YS3  ") == "912828YS3"


# ── MBS maturity labels ─────────────────────────────────────────────────────


def test_a_hyphenated_mbs_label_keeps_its_final_segment() -> None:
    assert _mbs_date("FNMA-30YR-2054") == "2054"


def test_an_unhyphenated_label_is_returned_trimmed() -> None:
    assert _mbs_date("  2054  ") == "2054"


@pytest.mark.parametrize("value", [None, "", 0])
def test_an_empty_mbs_label_is_none(value: object) -> None:
    assert _mbs_date(value) is None


# ── iShares CSV ─────────────────────────────────────────────────────────────


def test_the_header_row_is_located_beneath_the_preamble() -> None:
    csv = "\n".join(
        [
            "iShares Fund",
            "Fund Holdings as of,Aug 21 2026",
            '"Name","Sector","Weight (%)","Price"',
            '"T 4.5 2030","Treasury","1.20","99.5"',
        ]
    )

    assert _ishares_csv_header_row(csv) == 2


def test_a_csv_with_no_header_row_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="header row not found"):
        _ishares_csv_header_row("some,random,columns\n1,2,3")


@pytest.mark.parametrize("body", ["<!doctype html><html></html>", "  <html><body>Blocked"])
def test_an_html_response_is_reported_distinctly_from_a_bad_csv(body: str) -> None:
    with pytest.raises(RuntimeError, match="HTML page"):
        _ishares_csv_header_row(body)


def test_the_fund_document_request_names_the_requested_portfolio() -> None:
    params = _ishares_fund_document_params("239468")

    assert params["portfolioId"] == "239468"
    assert params["component"] == "holdings"
