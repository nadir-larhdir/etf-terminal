from fixed_income.analytics import DurationModelSelector
from fixed_income.instruments.security import Security


def test_duration_model_selector_routes_credit_and_treasury_buckets() -> None:
    selector = DurationModelSelector()

    lqd = Security("LQD", name="Investment Grade Corporate Bond ETF", asset_class="IG Credit")
    hyg = Security("HYG", name="High Yield Corporate Bond ETF", asset_class="HY Credit")
    tip = Security("TIP", name="TIPS Bond ETF", asset_class="Inflation-Linked")

    lqd_selection = selector.select_for_security(lqd, rough_duration=7.0)
    hyg_selection = selector.select_for_security(hyg, rough_duration=4.0)
    tip_selection = selector.select_for_security(tip, rough_duration=5.0)

    assert lqd_selection.asset_bucket == "Investment Grade Credit"
    assert lqd_selection.treasury_benchmark_symbol == "IEF"
    assert lqd_selection.spread_proxy_series_id == "BAMLC0A0CM"

    assert hyg_selection.asset_bucket == "High Yield"
    assert hyg_selection.treasury_benchmark_symbol == "SHY"
    assert hyg_selection.spread_proxy_series_id == "BAMLH0A0HYM2"

    assert tip_selection.duration_model_type == "treasury_curve_regression"
    assert tip_selection.treasury_benchmark_symbol is None


def test_duration_model_selector_uses_short_duration_fallback_for_sgov() -> None:
    selector = DurationModelSelector()
    sgov = Security("SGOV", name="Treasury Bill ETF", asset_class="UST Short")

    selection = selector.select_for_security(sgov)

    assert selection.asset_bucket == "Short Duration / Cash-like"
    assert selection.treasury_benchmark_symbol == "SHY"
    assert selection.used_fallback is True
