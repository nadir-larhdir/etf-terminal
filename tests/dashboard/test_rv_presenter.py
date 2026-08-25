from __future__ import annotations

import pytest

from dashboard.presenters.rv import DOWN, INK, UP, MetricCard, PillBadge, RVPresenter
from dashboard.render import render
from fixed_income.rv.signals import SignalRegime

PRESENTER = RVPresenter()


def _cards(**overrides: float | int) -> dict[str, MetricCard]:
    kwargs: dict[str, float | int] = {
        "zscore": 0.0,
        "stability": 60.0,
        "deviation_percent": 0.0,
        "fair_value_percent": 0.0,
        "forward_return_percent": 0.0,
        "hit_rate": 0.5,
        "event_count": 10,
    }
    kwargs.update(overrides)
    return {card.label: card for card in PRESENTER.top_cards(**kwargs)}  # type: ignore[arg-type]


# ── signal colouring ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("regime", "color"),
    [
        (SignalRegime.RICH, DOWN),
        (SignalRegime.RICH_EXTREME, DOWN),
        (SignalRegime.CHEAP, UP),
        (SignalRegime.CHEAP_EXTREME, UP),
        (SignalRegime.NEUTRAL, INK),
    ],
)
def test_rich_reads_as_a_short_and_cheap_as_a_long(regime: SignalRegime, color: str) -> None:
    assert PRESENTER.signal_color(regime) == color


# ── headline cards ──────────────────────────────────────────────────────────


def test_the_four_headline_cards_are_always_present() -> None:
    assert set(_cards()) == {"RV Signal", "Regime", "Dislocation", "Fwd Return (20D)"}


def test_the_signal_card_reports_the_regime_and_its_z_score() -> None:
    card = _cards(zscore=2.4)["RV Signal"]

    assert card.value == "RICH"
    assert card.sub_value == "2.40"
    assert card.color == DOWN


def test_a_cheap_signal_is_coloured_as_a_long() -> None:
    assert _cards(zscore=-2.4)["RV Signal"].color == UP


def test_a_neutral_signal_uses_plain_ink() -> None:
    assert _cards(zscore=0.3)["RV Signal"].color == INK


def test_the_regime_card_drops_the_extremity_qualifier() -> None:
    assert _cards(zscore=2.5)["Regime"].value == "RICH"


def test_the_regime_card_reports_stability_out_of_one_hundred() -> None:
    assert _cards(stability=73.4)["Regime"].sub_value == "73 / 100"


def test_a_positive_dislocation_is_coloured_rich() -> None:
    card = _cards(deviation_percent=1.25, fair_value_percent=-0.4)["Dislocation"]

    assert card.value == "+1.25%"
    assert card.sub_value == "-0.40%"
    assert card.color == DOWN


def test_a_negative_dislocation_is_coloured_cheap() -> None:
    assert _cards(deviation_percent=-1.25)["Dislocation"].color == UP


def test_the_forward_return_card_reports_the_hit_rate_as_a_fraction_of_events() -> None:
    card = _cards(forward_return_percent=0.85, hit_rate=0.6, event_count=15)["Fwd Return (20D)"]

    assert card.value == "+0.85%"
    assert card.sub_value == "60% (9/15)"
    assert card.color == UP


def test_a_negative_forward_return_is_coloured_down() -> None:
    assert _cards(forward_return_percent=-0.85)["Fwd Return (20D)"].color == DOWN


def test_a_study_with_no_events_still_renders() -> None:
    card = _cards(hit_rate=0.0, event_count=0)["Fwd Return (20D)"]

    assert card.sub_value == "0% (0/0)"


# ── ADF label ───────────────────────────────────────────────────────────────


def test_a_stationary_spread_is_labelled_mean_reverting() -> None:
    assert PRESENTER.adf_label(0.0123, True) == "0.0123 (MR)"


def test_a_non_stationary_spread_is_labelled_as_such() -> None:
    assert PRESENTER.adf_label(0.4210, False) == "0.4210 (No MR)"


@pytest.mark.parametrize(("pvalue", "stationary"), [(None, True), (0.01, None), (None, None)])
def test_an_incomplete_adf_result_shows_a_placeholder(
    pvalue: float | None, stationary: bool | None
) -> None:
    assert PRESENTER.adf_label(pvalue, stationary) == "--"


# ── badges and templates ────────────────────────────────────────────────────


@pytest.mark.parametrize("label", ["WATCH", "HOLD"])
def test_each_known_pill_has_its_own_colour(label: str) -> None:
    badge = PillBadge.from_label(label)

    assert badge.label == label
    assert badge.color == PillBadge.STYLES[label][0]


def test_an_unknown_pill_falls_back_to_the_hold_styling() -> None:
    assert PillBadge.from_label("MYSTERY").color == PillBadge.STYLES["HOLD"][0]


def test_the_pill_template_renders_the_label_and_its_colour() -> None:
    html = render("rv/pill_badge.html", badge=PillBadge.from_label("WATCH"))

    assert "WATCH" in html and "#C4882A" in html


def test_the_metric_grid_renders_one_card_per_entry() -> None:
    html = render("rv/metric_grid.html", cards=list(_cards().values()))

    assert html.count("rv-metric-card") == 4


def test_a_card_without_a_sub_reading_omits_the_sub_block() -> None:
    html = render("rv/metric_card.html", card=MetricCard("Label", "Value"))

    assert "rv-metric-sub" not in html
