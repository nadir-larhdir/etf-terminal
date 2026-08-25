from __future__ import annotations

import pytest

from fixed_income.rv.signals import SignalRegime


@pytest.mark.parametrize(
    ("zscore", "expected"),
    [
        (3.0, SignalRegime.RICH_EXTREME),
        (2.0, SignalRegime.RICH_EXTREME),
        (1.9, SignalRegime.RICH),
        (1.0, SignalRegime.RICH),
        (0.99, SignalRegime.NEUTRAL),
        (0.0, SignalRegime.NEUTRAL),
        (-0.99, SignalRegime.NEUTRAL),
        (-1.0, SignalRegime.CHEAP),
        (-1.9, SignalRegime.CHEAP),
        (-2.0, SignalRegime.CHEAP_EXTREME),
        (-3.0, SignalRegime.CHEAP_EXTREME),
    ],
)
def test_from_zscore_classifies_at_the_threshold_boundaries(
    zscore: float, expected: SignalRegime
) -> None:
    assert SignalRegime.from_zscore(zscore) is expected


def test_from_zscore_treats_nan_as_neutral() -> None:
    assert SignalRegime.from_zscore(float("nan")) is SignalRegime.NEUTRAL


@pytest.mark.parametrize(
    ("regime", "label", "compact", "threshold"),
    [
        (SignalRegime.RICH_EXTREME, "RICH / EXTREME", "RICH", "+2σ"),
        (SignalRegime.RICH, "RICH", "RICH", "+1σ"),
        (SignalRegime.NEUTRAL, "NEUTRAL", "NEUTRAL", ""),
        (SignalRegime.CHEAP, "CHEAP", "CHEAP", "-1σ"),
        (SignalRegime.CHEAP_EXTREME, "CHEAP / EXTREME", "CHEAP", "-2σ"),
    ],
)
def test_labels_match_the_legacy_display_strings(
    regime: SignalRegime, label: str, compact: str, threshold: str
) -> None:
    assert (regime.label, regime.compact_label, regime.threshold) == (label, compact, threshold)


def test_only_two_sigma_breaches_count_as_extreme() -> None:
    extreme = {r for r in SignalRegime if r.is_extreme}

    assert extreme == {SignalRegime.RICH_EXTREME, SignalRegime.CHEAP_EXTREME}


def test_action_is_watch_once_dislocated_and_hold_otherwise() -> None:
    assert SignalRegime.NEUTRAL.action == "HOLD"
    assert {r.action for r in SignalRegime if r is not SignalRegime.NEUTRAL} == {"WATCH"}


def test_trade_bias_names_both_legs_in_the_right_direction() -> None:
    assert SignalRegime.RICH_EXTREME.trade_bias("LQD", "IEF") == "Fade rich: Short LQD / Long IEF"
    assert SignalRegime.CHEAP_EXTREME.trade_bias("LQD", "IEF") == "Fade cheap: Long LQD / Short IEF"


def test_trade_bias_is_flat_when_neutral() -> None:
    assert SignalRegime.NEUTRAL.trade_bias("LQD", "IEF") == "No strong RV dislocation signal"
