from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fixed_income.etfs import ETF
from tests.fakes import FakeMetadataStore, FakePriceStore


def _history(
    closes: list[float],
    *,
    adj: list[float] | None = None,
    volumes: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> pd.DataFrame:
    n = len(closes)
    return pd.DataFrame(
        {
            "open": closes,
            "high": highs or [c * 1.01 for c in closes],
            "low": lows or [c * 0.99 for c in closes],
            "close": closes,
            "adj_close": adj or closes,
            "volume": volumes or [1_000_000.0] * n,
        },
        index=pd.bdate_range("2026-01-05", periods=n),
    )


# ── construction and loading ────────────────────────────────────────────────


def test_a_bare_etf_reports_no_history() -> None:
    etf = ETF("LQD")

    assert etf.has_history is False
    assert etf.last_price() is None
    assert etf.last_volume() is None


def test_set_history_copies_so_later_mutation_does_not_leak_in() -> None:
    frame = _history([100.0, 101.0])
    etf = ETF("LQD")
    etf.set_history(frame)

    frame.loc[frame.index[0], "close"] = 999.0

    assert float(etf.history["close"].iloc[0]) == 100.0


def test_set_metadata_defaults_none_to_an_empty_mapping() -> None:
    etf = ETF("LQD", metadata={"duration": 6.0})
    etf.set_metadata(None)

    assert etf.metadata == {}


def test_load_history_pulls_from_the_price_store() -> None:
    store = FakePriceStore({"LQD": _history([100.0, 101.0])})
    etf = ETF("LQD")

    loaded = etf.load_history(store)

    assert len(loaded) == 2
    assert etf.has_history


def test_load_metadata_pulls_from_the_metadata_store() -> None:
    store = FakeMetadataStore({"LQD": {"duration": 6.4}})
    etf = ETF("LQD")

    assert etf.load_metadata(store) == {"duration": 6.4}
    assert etf.metadata_number("duration") == pytest.approx(6.4)


def test_load_metadata_of_an_unknown_ticker_yields_an_empty_mapping() -> None:
    assert ETF("NOPE").load_metadata(FakeMetadataStore()) == {}


# ── provider metadata parsing ───────────────────────────────────────────────


@pytest.mark.parametrize("raw", [None, "", "N/A", "not-a-number", float("nan")])
def test_metadata_number_treats_every_missing_marker_as_none(raw: object) -> None:
    assert ETF("LQD", metadata={"duration": raw}).metadata_number("duration") is None


def test_metadata_number_is_none_for_an_absent_key() -> None:
    assert ETF("LQD").metadata_number("duration") is None


@pytest.mark.parametrize("raw", [6.4, "6.4", 6])
def test_metadata_number_parses_numeric_strings_and_ints(raw: object) -> None:
    assert ETF("LQD", metadata={"duration": raw}).metadata_number("duration") == pytest.approx(
        float(raw)  # type: ignore[arg-type]
    )


# ── price series ────────────────────────────────────────────────────────────


def test_last_price_and_volume_read_the_final_row() -> None:
    etf = ETF("LQD", history=_history([100.0, 105.0], volumes=[1.0, 2.0]))

    assert etf.last_price() == 105.0
    assert etf.last_volume() == 2.0


def test_adjusted_close_is_preferred_over_close() -> None:
    etf = ETF("LQD", history=_history([100.0, 100.0], adj=[50.0, 60.0]))

    assert etf.adj_close_series().tolist() == [50.0, 60.0]


def test_adjusted_close_falls_back_to_close_when_absent() -> None:
    frame = _history([100.0, 101.0]).drop(columns=["adj_close"])

    assert ETF("LQD", history=frame).adj_close_series().tolist() == [100.0, 101.0]


@pytest.mark.parametrize(
    "accessor",
    ["close_series", "adj_close_series", "volume_series", "returns", "log_returns"],
)
def test_every_series_accessor_is_empty_without_history(accessor: str) -> None:
    assert getattr(ETF("LQD"), accessor)().empty


def test_returns_are_computed_off_the_adjusted_series() -> None:
    etf = ETF("LQD", history=_history([100.0, 100.0], adj=[100.0, 110.0]))

    assert etf.returns().iloc[-1] == pytest.approx(0.1)


def test_log_returns_match_the_analytic_value() -> None:
    etf = ETF("LQD", history=_history([100.0, 110.0]))

    assert etf.log_returns().iloc[-1] == pytest.approx(np.log(1.1))


def test_log_returns_stay_finite_across_a_zero_price() -> None:
    etf = ETF("LQD", history=_history([100.0, 0.0, 110.0]))

    assert np.isfinite(etf.log_returns()).all()


def test_normalized_price_rebases_to_the_given_start() -> None:
    etf = ETF("LQD", history=_history([50.0, 75.0]))

    assert etf.normalized_price(100.0).tolist() == [100.0, 150.0]


def test_normalized_price_of_a_zero_start_is_undefined_rather_than_infinite() -> None:
    etf = ETF("LQD", history=_history([0.0, 75.0]))

    assert etf.normalized_price().isna().all()


def test_normalized_price_without_history_is_empty() -> None:
    assert ETF("LQD").normalized_price().empty


def test_rolling_volume_mean_averages_over_the_window() -> None:
    etf = ETF("LQD", history=_history([100.0] * 4, volumes=[10.0, 20.0, 30.0, 40.0]))

    assert etf.rolling_volume_mean(window=2).iloc[-1] == pytest.approx(35.0)


# ── slicing and the trading snapshot ────────────────────────────────────────


def test_history_between_restricts_to_the_requested_range() -> None:
    etf = ETF("LQD", history=_history([100.0, 101.0, 102.0, 103.0]))
    index = etf.history.index

    assert len(etf.history_between(index[1], index[2])) == 2


def test_history_between_falls_back_to_the_last_row_when_the_range_is_empty() -> None:
    etf = ETF("LQD", history=_history([100.0, 101.0]))

    sliced = etf.history_between("2030-01-01", "2030-12-31")

    assert len(sliced) == 1
    assert float(sliced["close"].iloc[0]) == 101.0


def test_history_between_without_history_stays_empty() -> None:
    assert ETF("LQD").history_between("2026-01-01", "2026-12-31").empty


def test_the_trading_snapshot_is_all_none_without_history() -> None:
    snapshot = ETF("LQD").trading_snapshot()

    assert snapshot == {
        "latest_price": None,
        "current_volume": None,
        "average_volume": None,
        "volume_z": None,
        "range_position": None,
    }


def test_the_trading_snapshot_reports_price_and_volume() -> None:
    etf = ETF("LQD", history=_history([100.0] * 5, volumes=[10.0, 10.0, 10.0, 10.0, 20.0]))

    snapshot = etf.trading_snapshot(volume_window=5)

    assert snapshot["latest_price"] == 100.0
    assert snapshot["current_volume"] == 20.0
    assert snapshot["average_volume"] == pytest.approx(12.0)


def test_volume_z_is_positive_on_an_unusually_heavy_day() -> None:
    etf = ETF("LQD", history=_history([100.0] * 5, volumes=[10.0, 11.0, 9.0, 10.0, 40.0]))

    volume_z = etf.trading_snapshot(volume_window=5)["volume_z"]

    assert volume_z is not None and volume_z > 1.0


def test_volume_z_is_undefined_when_volume_never_varies() -> None:
    etf = ETF("LQD", history=_history([100.0] * 5, volumes=[10.0] * 5))

    assert etf.trading_snapshot(volume_window=5)["volume_z"] is None


def test_range_position_places_the_close_within_the_day_range() -> None:
    etf = ETF("LQD", history=_history([100.0], highs=[110.0], lows=[90.0]))

    assert etf.trading_snapshot()["range_position"] == pytest.approx(0.5)


def test_range_position_defaults_to_the_midpoint_on_a_zero_range_day() -> None:
    etf = ETF("LQD", history=_history([100.0], highs=[100.0], lows=[100.0]))

    assert etf.trading_snapshot()["range_position"] == 0.5
