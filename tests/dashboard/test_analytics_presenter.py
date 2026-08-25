from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from dashboard.presenters.analytics import (
    ALERT,
    CS01_PER_MILLION,
    CS_BETA_BPS,
    DURATION_YEARS,
    DV01_PER_MILLION,
    GOOD,
    INK,
    MODEL_FIT,
    WARN,
    AnalyticsPresenter,
    DurationScale,
    Gauge,
    RiskScale,
)
from dashboard.render import render
from fixed_income.analytics.result_models import (
    ETFAnalyticsSnapshot,
    RateRiskEstimate,
    SpreadRiskEstimate,
)
from fixed_income.etfs import ETF

PRESENTER = AnalyticsPresenter()


def _snapshot(
    *,
    duration: float | None = 6.4,
    dv01: float | None = 0.024,
    proxy: str | None = "BAMLC0A0CM",
    beta: float | None = -0.00012,
    r2: float | None = 0.62,
    observations: int | None = 120,
) -> ETFAnalyticsSnapshot:
    return ETFAnalyticsSnapshot(
        ticker="LQD",
        asset_bucket="Investment Grade Credit",
        model_type_used="provider_metadata",
        confidence_level="high",
        notes="",
        reason=None,
        rate_risk=RateRiskEstimate(
            estimated_duration=duration, dv01_per_share=dv01, observations_used=observations
        ),
        spread_risk=(
            SpreadRiskEstimate(
                beta_per_bp=beta, dv01_proxy_per_share=0.012, regression_r2=r2, proxy_used=proxy
            )
            if proxy
            else None
        ),
    )


def _etf(**metadata: object) -> ETF:
    return ETF("LQD", asset_class="IG Credit", metadata=metadata)


def _history(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"adj_close": closes, "close": closes, "volume": [1_000_000.0] * len(closes)},
        index=pd.bdate_range("2026-01-05", periods=len(closes)),
    )


# ── risk colouring ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "color"), [(2.0, GOOD), (3.0, GOOD), (5.0, WARN), (7.0, WARN), (12.0, ALERT)]
)
def test_duration_colours_step_at_its_thresholds(value: float, color: str) -> None:
    assert DURATION_YEARS.color(value) == color


@pytest.mark.parametrize(("per_share", "color"), [(0.010, GOOD), (0.030, WARN), (0.080, ALERT)])
def test_dv01_is_coloured_on_its_per_million_magnitude(per_share: float, color: str) -> None:
    assert DV01_PER_MILLION.color(per_share) == color


def test_a_negative_sensitivity_is_coloured_on_its_magnitude() -> None:
    assert CS_BETA_BPS.color(-0.00050) == CS_BETA_BPS.color(0.00050)


@pytest.mark.parametrize(
    "scale", [DURATION_YEARS, DV01_PER_MILLION, CS_BETA_BPS, CS01_PER_MILLION, MODEL_FIT]
)
def test_an_unavailable_value_is_neutral_ink(scale: RiskScale) -> None:
    assert scale.color(None) == INK


@pytest.mark.parametrize(("r2", "color"), [(0.10, ALERT), (0.40, WARN), (0.85, GOOD)])
def test_model_fit_colours_invert_because_a_higher_r2_is_better(r2: float, color: str) -> None:
    assert MODEL_FIT.color(r2) == color


# ── metric cards ────────────────────────────────────────────────────────────


def test_instrument_cards_format_each_field_in_its_own_unit() -> None:
    etf = _etf(yield_to_maturity=4.82, oas=118.0, years_to_maturity=8.4, convexity=0.94)

    cards = {card.label: card.value for card in PRESENTER.instrument_cards(etf)}

    assert cards["YTM (SEC)"] == "4.82%"
    assert cards["OAS"] == "118 bps"
    assert cards["Years to Maturity"] == "8.4y"
    assert cards["Convexity"] == "0.94"


def test_instrument_cards_show_placeholders_when_metadata_is_absent() -> None:
    values = {card.value for card in PRESENTER.instrument_cards(_etf())}

    assert values == {"-"}


def test_rate_risk_cards_report_duration_and_dv01_per_million() -> None:
    cards = {
        card.label: card.value
        for card in PRESENTER.rate_risk_cards(
            _snapshot(), duration_method="Provider", duration_source="metadata"
        )
    }

    assert cards["Est. Duration"] == "6.4y"
    assert cards["DV01 / $1MM"] == "$240"
    assert cards["Duration Method"] == "Provider"


def test_spread_cards_are_omitted_without_a_proxy() -> None:
    assert PRESENTER.spread_risk_cards(_snapshot(proxy=None)) == []


def test_spread_cards_are_omitted_when_the_beta_never_fitted() -> None:
    assert PRESENTER.spread_risk_cards(_snapshot(beta=None)) == []


def test_spread_cards_label_the_proxy_readably() -> None:
    cards = {card.label: card.value for card in PRESENTER.spread_risk_cards(_snapshot())}

    assert cards["OAS Proxy Used"] == "BoFA IG OAS"
    assert cards["CS Beta"] == "-1.2 bps"
    assert cards["Credit Spread R²"] == "0.62"


def test_the_last_spread_card_drops_its_bottom_border() -> None:
    assert PRESENTER.spread_risk_cards(_snapshot())[-1].show_bottom_border is False


# ── gauges and scales ───────────────────────────────────────────────────────


@pytest.mark.parametrize(("value", "percent"), [(0.0, 0.0), (0.5, 50.0), (1.0, 100.0)])
def test_the_fit_gauge_maps_r2_onto_a_percentage(value: float, percent: float) -> None:
    gauge = Gauge.from_fraction(value)

    assert gauge is not None and gauge.percent == pytest.approx(percent)


@pytest.mark.parametrize("value", [-0.5, 1.5])
def test_the_fit_gauge_clamps_out_of_range_values(value: float) -> None:
    gauge = Gauge.from_fraction(value)

    assert gauge is not None and 0.0 <= gauge.percent <= 100.0


def test_there_is_no_gauge_without_a_fit() -> None:
    assert Gauge.from_fraction(None) is None


def test_the_duration_scale_places_the_marker_proportionally() -> None:
    scale = DurationScale.from_years(15.0)

    assert scale is not None and scale.percent == pytest.approx(50.0)


def test_the_duration_scale_clamps_beyond_its_axis() -> None:
    scale = DurationScale.from_years(60.0)

    assert scale is not None and scale.percent == 100.0


def test_there_is_no_duration_scale_without_a_duration() -> None:
    assert DurationScale.from_years(None) is None


# ── liquidity and narrative ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("volume_z", "regime"),
    [(3.0, "HIGH ACTIVITY"), (2.0, "NORMAL"), (0.0, "NORMAL"), (-1.5, "QUIET"), (None, "NORMAL")],
)
def test_liquidity_regime_classifies_participation(volume_z: float | None, regime: str) -> None:
    assert PRESENTER.liquidity_regime(volume_z) == regime


def test_the_liquidity_summary_quotes_volume_against_its_average() -> None:
    etf = ETF("LQD", history=_history([100.0] * 31))

    assert "x1.00" in PRESENTER.liquidity_summary(etf)


def test_the_dv01_footer_reports_a_thirty_day_move() -> None:
    etf = ETF("LQD", history=_history([100.0] * 31 + [110.0]))

    footer = PRESENTER.dv01_change_footer(etf, duration=6.0)

    assert footer is not None and footer.startswith("30d ↑")


def test_the_dv01_footer_marks_a_decline_with_a_down_arrow() -> None:
    etf = ETF("LQD", history=_history([110.0] * 31 + [100.0]))

    footer = PRESENTER.dv01_change_footer(etf, duration=6.0)

    assert footer is not None and "↓" in footer


def test_there_is_no_dv01_footer_without_enough_history() -> None:
    etf = ETF("LQD", history=_history([100.0, 101.0]))

    assert PRESENTER.dv01_change_footer(etf, duration=6.0) is None


def test_there_is_no_dv01_footer_without_a_duration() -> None:
    etf = ETF("LQD", history=_history([100.0] * 40))

    assert PRESENTER.dv01_change_footer(etf, duration=None) is None


def test_the_read_headline_combines_the_bucket_and_category() -> None:
    etf = _etf(category="IG Credit", duration_bucket="Belly")

    assert PRESENTER.read_headline(etf) == "Belly IG Credit"


@pytest.mark.parametrize("bucket", ["", "  ", "N/A", "n/a"])
def test_the_read_headline_omits_an_unknown_bucket(bucket: str) -> None:
    etf = _etf(category="IG Credit", duration_bucket=bucket)

    assert PRESENTER.read_headline(etf) == "IG Credit"


def test_the_read_headline_falls_back_to_the_asset_class() -> None:
    assert PRESENTER.read_headline(_etf()) == "IG Credit"


def test_the_read_body_names_the_benchmark_duration_and_dv01() -> None:
    etf = _etf(benchmark_index="Markit iBoxx")

    body = PRESENTER.read_body(
        etf, _snapshot(), duration_method="Provider", duration_source="metadata"
    )

    assert "Markit iBoxx" in body and "6.4y" in body and "$240" in body


def test_the_oas_explanation_states_the_price_impact_of_one_basis_point() -> None:
    assert "-1.20 bps" in PRESENTER.oas_move_explanation(_snapshot())


def test_the_oas_explanation_is_unavailable_without_a_fitted_spread() -> None:
    assert "unavailable" in PRESENTER.oas_move_explanation(_snapshot(proxy=None))


# ── templates ───────────────────────────────────────────────────────────────


def test_the_metric_card_template_renders_its_value_and_colour() -> None:
    card = PRESENTER.instrument_cards(_etf(yield_to_maturity=4.82))[0]

    html = render("analytics/metric_card.html", card=card, footer=None)

    assert "4.82%" in html and card.color in html


def test_the_metric_card_template_omits_an_absent_footer() -> None:
    card = PRESENTER.instrument_cards(_etf())[0]

    assert "an-metric-footer" not in render("analytics/metric_card.html", card=card, footer=None)


def test_the_fit_footer_renders_the_gauge_and_observation_count() -> None:
    html = render("analytics/fit_footer.html", gauge=Gauge.from_fraction(0.62), observations=120)

    assert "62.0%" in html and "120 observations" in html


def test_the_fit_footer_drops_the_gauge_when_there_is_no_fit() -> None:
    html = render("analytics/fit_footer.html", gauge=None, observations="N/A")

    assert "an-gauge-track" not in html
    assert "N/A observations" in html


def test_the_read_panel_template_renders_all_three_slots() -> None:
    html = render(
        "analytics/read_panel.html", kicker="Current Read", headline="Belly IG", body="Body copy."
    )

    assert "Current Read" in html and "Belly IG" in html and "Body copy." in html


def test_a_snapshot_without_spread_risk_reports_no_spread_fields() -> None:
    analytics = _snapshot(proxy=None)

    assert AnalyticsPresenter.has_spread_risk(analytics) is False
    assert analytics.spread_proxy_used is None


def test_a_namespace_shaped_snapshot_is_accepted_by_has_spread_risk() -> None:
    assert (
        AnalyticsPresenter.has_spread_risk(
            SimpleNamespace(spread_proxy_used="X", spread_beta_per_bp=0.1)
        )
        is True
    )
