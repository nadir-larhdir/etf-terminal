from __future__ import annotations

import pytest

from fixed_income.etfs.holdings import _ishares_csv_header_row


def test_ishares_csv_header_row_detects_variable_preamble() -> None:
    text = "\n".join(
        [
            "iShares Fund Holdings",
            "as of,2026-05-21",
            "Name,CUSIP,Sector,Asset Class,Weight (%),Market Value,Par Value",
            "Apple Inc,037833AL4,Corporate,Bond,1.23,1000,1000",
        ]
    )

    assert _ishares_csv_header_row(text) == 2


def test_ishares_csv_header_row_rejects_html_response() -> None:
    with pytest.raises(RuntimeError, match="HTML page"):
        _ishares_csv_header_row("<!DOCTYPE html><html><head></head></html>")
