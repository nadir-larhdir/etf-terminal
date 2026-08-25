from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from fixed_income.rv.spread_diagnostics import (
    TRADING_DAYS,
    breach_events,
    build_spread_frame,
    cumulative_spread,
    diagnose_spread,
    estimate_beta,
    event_study,
    forward_spread_reversion_stats,
    half_life,
    hurst_exponent,
    lag1_autocorr,
    load_pair_prices,
    log_returns,
    regime_from_zscore,
    rolling_beta,
    spread_stability_score,
    zero_crossings,
)
from tests.fakes import FakePriceStore

SPREAD_COLUMNS = ["close_left", "close_right"]


def _prices(left: list[float], right: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {"close_left": left, "close_right": right},
        index=pd.bdate_range("2025-01-01", periods=len(left)),
        dtype=float,
    )


def _mean_reverting(n: int = 400, *, half_life_days: float = 5.0, seed: int = 3) -> pd.DataFrame:
    """Build a pair whose price spread is a stationary OU process with a known half-life."""
    rng = np.random.default_rng(seed)
    phi = 0.5 ** (1.0 / half_life_days)
    spread = np.zeros(n)
    for i in range(1, n):
        spread[i] = phi * spread[i - 1] + rng.normal(0.0, 1.0)
    right = 100.0 + np.cumsum(rng.normal(0.0, 0.2, n))
    return _prices((right + spread).tolist(), right.tolist())


def _random_walk_pair(n: int = 300, seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    left = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    right = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    return _prices(left.tolist(), right.tolist())


# ── returns and beta ────────────────────────────────────────────────────────


def test_log_returns_rename_the_two_legs() -> None:
    assert list(log_returns(_prices([100, 101], [50, 51])).columns) == ["ret_left", "ret_right"]


def test_log_returns_of_an_empty_frame_keep_the_leg_columns() -> None:
    assert list(log_returns(pd.DataFrame()).columns) == ["ret_left", "ret_right"]


def test_estimate_beta_recovers_a_known_ratio_of_returns() -> None:
    rng = np.random.default_rng(11)
    steps = rng.normal(0.0, 0.01, 200)
    right = 100.0 * np.exp(np.cumsum(steps))
    left = 100.0 * np.exp(np.cumsum(steps * 2.0))

    assert estimate_beta(_prices(left.tolist(), right.tolist())) == pytest.approx(2.0, abs=0.02)


def test_estimate_beta_falls_back_on_an_empty_frame() -> None:
    assert estimate_beta(pd.DataFrame(columns=SPREAD_COLUMNS), default=0.9) == 0.9


def test_estimate_beta_falls_back_when_the_hedge_leg_never_moves() -> None:
    assert estimate_beta(_prices([100, 101, 102], [50, 50, 50]), default=0.4) == 0.4


def test_full_sample_and_trailing_beta_differ_when_the_relationship_shifts() -> None:
    prices = _mean_reverting()

    trailing = estimate_beta(prices, lookback=30, source="trailing")
    full = estimate_beta(prices, source="full_sample")

    assert trailing != full


def test_rolling_beta_is_nan_where_the_hedge_leg_has_no_variance() -> None:
    returns = pd.DataFrame({"ret_left": [0.01] * 30, "ret_right": [0.0] * 30})

    assert rolling_beta(returns, window=10).dropna().empty


# ── spread frame ────────────────────────────────────────────────────────────


def test_build_spread_frame_of_empty_prices_keeps_its_schema() -> None:
    frame = build_spread_frame(pd.DataFrame(), beta=1.0)

    assert frame.empty
    assert {"spread", "zscore", "rolling_beta"} <= set(frame.columns)


def test_price_spread_removes_the_hedged_leg() -> None:
    frame = build_spread_frame(_prices([100.0] * 30, [50.0] * 30), beta=2.0)

    assert frame["spread"].dropna().unique().tolist() == [0.0]


def test_return_spread_uses_returns_rather_than_levels() -> None:
    prices = _mean_reverting(120)

    price_frame = build_spread_frame(prices, beta=1.0, spread_kind="price")
    return_frame = build_spread_frame(prices, beta=1.0, spread_kind="return")

    assert price_frame["spread"].abs().mean() > return_frame["spread"].abs().mean()


def test_zscore_is_nan_where_the_spread_is_perfectly_flat() -> None:
    frame = build_spread_frame(_prices([100.0] * 40, [50.0] * 40), beta=2.0, z_window=20)

    assert frame["zscore"].dropna().empty


def test_zscore_matches_the_rolling_mean_and_deviation() -> None:
    frame = build_spread_frame(_mean_reverting(120), beta=1.0, z_window=20)
    row = frame.dropna(subset=["zscore"]).iloc[-1]

    assert row["zscore"] == pytest.approx((row["spread"] - row["spread_mean"]) / row["spread_std"])


# ── mean-reversion diagnostics ──────────────────────────────────────────────


def test_lag1_autocorr_is_undefined_for_a_series_that_is_too_short() -> None:
    assert lag1_autocorr(pd.Series([1.0, 2.0])) is None


def test_lag1_autocorr_is_high_for_a_persistent_series() -> None:
    persistent = pd.Series(np.linspace(0, 10, 50))

    assert lag1_autocorr(persistent) == pytest.approx(1.0, abs=0.05)


def test_half_life_recovers_the_ou_decay_it_was_built_with() -> None:
    frame = build_spread_frame(_mean_reverting(600, half_life_days=5.0), beta=1.0)

    estimate = half_life(frame["spread"].dropna())

    assert estimate is not None
    assert estimate == pytest.approx(5.0, rel=0.5)


def test_half_life_is_undefined_for_a_series_that_is_too_short() -> None:
    assert half_life(pd.Series([1.0, 2.0, 3.0])) is None


def test_half_life_is_undefined_for_a_trending_series_that_never_reverts() -> None:
    assert half_life(pd.Series(np.linspace(0.0, 100.0, 200))) is None


def test_cumulative_spread_sums_over_the_window() -> None:
    assert cumulative_spread(pd.Series([1.0, 2.0, 3.0]), window=2).iloc[-1] == pytest.approx(5.0)


def test_hurst_is_below_one_half_for_a_mean_reverting_spread() -> None:
    frame = build_spread_frame(_mean_reverting(600), beta=1.0)

    exponent = hurst_exponent(frame["spread"].dropna())

    assert exponent is not None and exponent < 0.5


def test_hurst_is_undefined_for_a_short_series() -> None:
    assert hurst_exponent(pd.Series(np.arange(10.0))) is None


def test_zero_crossings_count_sign_changes_around_the_mean() -> None:
    alternating = pd.Series([1.0, -1.0, 1.0, -1.0, 1.0])

    assert zero_crossings(alternating) == 4


def test_zero_crossings_of_a_monotonic_series_are_counted_once() -> None:
    assert zero_crossings(pd.Series(np.linspace(-5.0, 5.0, 11))) == 1


def test_zero_crossings_of_a_series_that_is_too_short_are_zero() -> None:
    assert zero_crossings(pd.Series([1.0])) == 0


# ── regime and stability ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("zscore", "label"),
    [
        (2.5, "RICH / EXTREME"),
        (1.2, "RICH"),
        (0.0, "NEUTRAL"),
        (-1.2, "CHEAP"),
        (-2.5, "CHEAP / EXTREME"),
    ],
)
def test_regime_from_zscore_matches_the_shared_signal_mapping(zscore: float, label: str) -> None:
    assert regime_from_zscore(zscore) == label


def test_stability_score_is_bounded_and_rewards_a_stationary_spread() -> None:
    _, stationary = diagnose_spread(_mean_reverting(600), left_ticker="LQD", right_ticker="IEF")
    _, drifting = diagnose_spread(_random_walk_pair(600), left_ticker="LQD", right_ticker="IEF")

    for diagnostics in (stationary, drifting):
        assert 0.0 <= spread_stability_score(diagnostics) <= 100.0
    assert spread_stability_score(stationary) > spread_stability_score(drifting)


# ── event studies ───────────────────────────────────────────────────────────


def test_breach_events_report_only_the_first_day_of_each_excursion() -> None:
    frame = pd.DataFrame(
        {
            "spread": np.arange(8.0),
            "zscore": [0.0, 2.5, 2.6, 2.7, 0.0, 0.0, 2.5, 0.0],
            "rolling_beta": 1.0,
        }
    )

    assert len(breach_events(frame, 2.0)) == 2


def test_breach_events_are_empty_when_nothing_breaches() -> None:
    frame = pd.DataFrame({"spread": [1.0] * 5, "zscore": [0.1] * 5, "rolling_beta": 1.0})

    assert breach_events(frame, 2.0).empty


def test_event_study_of_an_empty_frame_is_empty() -> None:
    assert event_study(pd.DataFrame()).empty


def test_event_study_reports_one_row_per_threshold_and_horizon_with_events() -> None:
    frame = build_spread_frame(_mean_reverting(600), beta=1.0)

    table = event_study(frame, thresholds=(1.5,), horizons=(1, 5))

    assert not table.empty
    assert set(table["horizon_d"]) <= {1, 5}
    assert (table["n_events"] > 0).all()


def test_event_study_annualises_events_against_the_trading_calendar() -> None:
    frame = build_spread_frame(_mean_reverting(TRADING_DAYS * 2), beta=1.0)

    table = event_study(frame, thresholds=(1.5,), horizons=(5,))

    row = table.iloc[0]
    assert row["events_per_year"] == pytest.approx(row["n_events"] / 2.0, rel=0.35)


def test_forward_reversion_stats_are_zero_without_any_breach() -> None:
    frame = build_spread_frame(_prices([100.0] * 60, [50.0] * 60), beta=2.0)

    assert forward_spread_reversion_stats(frame, 5) == (0.0, 0.0, 0)


def test_forward_reversion_stats_report_a_hit_rate_between_zero_and_one() -> None:
    frame = build_spread_frame(_mean_reverting(600), beta=1.0)

    _, hit_rate, count = forward_spread_reversion_stats(frame, 5)

    assert count > 0
    assert 0.0 <= hit_rate <= 1.0


# ── loading and the end-to-end summary ──────────────────────────────────────


def test_load_pair_prices_aligns_both_legs_on_shared_dates() -> None:
    index = pd.bdate_range("2025-01-01", periods=5)
    store = FakePriceStore(
        {
            "LQD": pd.DataFrame({"adj_close": np.arange(5.0) + 100}, index=index),
            "IEF": pd.DataFrame({"adj_close": np.arange(4.0) + 90}, index=index[:4]),
        }
    )

    prices = load_pair_prices(store, "LQD", "IEF")

    assert list(prices.columns) == SPREAD_COLUMNS
    assert len(prices) == 4


def test_load_pair_prices_is_empty_when_a_leg_is_missing() -> None:
    store = FakePriceStore({"LQD": pd.DataFrame({"adj_close": [100.0]})})

    assert load_pair_prices(store, "LQD", "IEF").empty


def test_diagnose_spread_summarises_a_stationary_pair() -> None:
    frame, diagnostics = diagnose_spread(
        _mean_reverting(600), left_ticker="LQD", right_ticker="IEF"
    )

    assert diagnostics.pair == "LQD / IEF"
    assert diagnostics.observations == len(frame["spread"].dropna())
    assert diagnostics.adf_is_stationary_5pct is True
    assert diagnostics.zero_crossings > 0
    assert not math.isnan(diagnostics.spread_std)


def test_diagnose_spread_of_an_empty_pair_reports_zeroed_fields() -> None:
    _, diagnostics = diagnose_spread(
        pd.DataFrame(columns=SPREAD_COLUMNS), left_ticker="LQD", right_ticker="IEF"
    )

    assert diagnostics.observations == 0
    assert diagnostics.sample_start == "" and diagnostics.sample_end == ""
    assert diagnostics.spread_last == 0.0 and diagnostics.zscore_last == 0.0


def test_diagnose_spread_records_which_beta_convention_was_used() -> None:
    _, diagnostics = diagnose_spread(
        _mean_reverting(200),
        left_ticker="LQD",
        right_ticker="IEF",
        beta_source="full_sample",
    )

    assert diagnostics.beta_source == "full_sample"


def test_diagnostics_round_trip_to_a_plain_dict() -> None:
    _, diagnostics = diagnose_spread(_mean_reverting(200), left_ticker="A", right_ticker="B")

    as_dict = diagnostics.as_dict()

    assert as_dict["pair"] == "A / B"
    assert as_dict["observations"] == diagnostics.observations
