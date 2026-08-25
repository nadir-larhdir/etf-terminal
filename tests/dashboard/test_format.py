from __future__ import annotations

import numpy as np
import pytest

from dashboard.format import Formatter, MacroUnit, macro_unit, to_number

FMT = Formatter()
NA = Formatter(missing="N/A")


@pytest.mark.parametrize("raw", [None, "", "abc", float("nan"), float("inf"), -np.inf, True])
def test_to_number_rejects_anything_that_is_not_a_finite_quantity(raw: object) -> None:
    assert to_number(raw) is None


@pytest.mark.parametrize("raw", ["4.37", 4, 4.37, np.float64(4.37)])
def test_to_number_accepts_numeric_strings_and_numpy_scalars(raw: object) -> None:
    assert to_number(raw) == pytest.approx(float(raw))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda f: f.number(1234.567), "1,234.57"),
        (lambda f: f.number(1234.567, 0), "1,235"),
        (lambda f: f.number(1.5, signed=True), "+1.50"),
        (lambda f: f.number(-1.5, signed=True), "-1.50"),
        (lambda f: f.percent(4.37), "4.37%"),
        (lambda f: f.percent(4.37, signed=True), "+4.37%"),
        (lambda f: f.proportion(0.85), "85%"),
        (lambda f: f.bps(412), "412 bps"),
        (lambda f: f.bps(-12.3, 1, signed=True), "-12.3 bps"),
        (lambda f: f.percent_as_bps(4.12), "412 bps"),
        (lambda f: f.years(5.24), "5.2y"),
        (lambda f: f.multiple(1.234), "x1.23"),
        (lambda f: f.money(12345), "$12,345"),
        (lambda f: f.money_per_million(0.42), "$4,200"),
        (lambda f: f.decimal_as_bps(0.00012), "+1.2 bps"),
        (lambda f: f.zscore(1.234), "z +1.23"),
    ],
)
def test_formatter_renders_each_unit_the_way_a_desk_quotes_it(call, expected: str) -> None:
    assert call(FMT) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1_200_000_000, "1.2B"),
        (450_000_000, "450.0M"),
        (12_500, "12.5K"),
        (999, "999"),
        (0, "0"),
        (-1_200_000_000, "-1.2B"),
    ],
)
def test_compact_uses_one_k_m_b_convention_across_the_app(value: float, expected: str) -> None:
    assert FMT.compact(value) == expected


@pytest.mark.parametrize(
    "call",
    [
        lambda f: f.number(None),
        lambda f: f.percent("n/a"),
        lambda f: f.bps(float("nan")),
        lambda f: f.years(None),
        lambda f: f.multiple(None),
        lambda f: f.money(None),
        lambda f: f.money_per_million(None),
        lambda f: f.decimal_as_bps(None),
        lambda f: f.compact(None),
        lambda f: f.zscore(None),
        lambda f: f.proportion(None),
        lambda f: f.percent_as_bps(None),
    ],
)
def test_every_formatter_falls_back_to_its_placeholder(call) -> None:
    assert call(FMT) == "-"
    assert call(NA) == "N/A"


@pytest.mark.parametrize(
    ("feature", "unit"),
    [
        ("IG_OAS_LEVEL", MacroUnit.BPS),
        ("HY_MINUS_IG_OAS", MacroUnit.BPS),
        ("IG_OAS_CHANGE_20D", MacroUnit.BPS),
        ("UST_2S10S", MacroUnit.BPS),
        ("UST_5S30S_CHANGE_20D", MacroUnit.BPS),
        ("UST_10Y_LEVEL", MacroUnit.PERCENT),
        ("BEI_5Y", MacroUnit.PERCENT),
        ("CPI_YOY", MacroUnit.PERCENT),
        ("FEDFUNDS_LEVEL", MacroUnit.PERCENT),
        ("UNRATE_LEVEL", MacroUnit.PERCENT),
        ("REAL_RATE_PROXY", MacroUnit.PERCENT),
        ("IG_OAS_Z60", MacroUnit.ZSCORE),
        ("UST_2S10S_Z20", MacroUnit.ZSCORE),
        ("SOMETHING_NEW", MacroUnit.PLAIN),
    ],
)
def test_macro_unit_resolves_from_the_feature_name(feature: str, unit: MacroUnit) -> None:
    assert macro_unit(feature) is unit


def test_z_score_suffix_wins_over_the_oas_stem() -> None:
    assert macro_unit("HY_OAS_Z60") is MacroUnit.ZSCORE


def test_the_same_feature_renders_identically_wherever_it_is_shown() -> None:
    curve = macro_unit("UST_2S10S")

    assert curve.level(0.50, FMT) == "50 bps"
    assert curve.delta(0.012, FMT) == "+1.2 bps"


def test_levels_keep_natural_units_while_moves_are_quoted_in_bps() -> None:
    rate = macro_unit("UST_10Y_LEVEL")

    assert rate.level(4.37, FMT) == "4.37%"
    assert rate.delta(0.031, FMT) == "+3.1 bps"


def test_zscore_features_read_as_scores_in_both_directions() -> None:
    z = macro_unit("IG_OAS_Z60")

    assert z.level(-1.2, FMT) == "z -1.20"
    assert z.delta(0.4, FMT) == "z +0.40"


@pytest.mark.parametrize("unit", list(MacroUnit))
def test_every_unit_renders_a_placeholder_for_missing_data(unit: MacroUnit) -> None:
    assert unit.level(None, FMT) == "-"
    assert unit.delta(None, FMT) == "-"
