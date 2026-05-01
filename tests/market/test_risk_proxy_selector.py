from fixed_income.analytics import RiskProxySelector
from fixed_income.etfs import ETF


def test_risk_proxy_selector_routes_credit_and_treasury_buckets() -> None:
    selector = RiskProxySelector()

    lqd = ETF("LQD", name="Investment Grade Corporate Bond ETF", asset_class="IG Credit")
    hyg = ETF("HYG", name="High Yield Corporate Bond ETF", asset_class="HY Credit")
    tip = ETF("TIP", name="TIPS Bond ETF", asset_class="Inflation-Linked")

    lqd_selection = selector.select_for_etf(lqd)
    hyg_selection = selector.select_for_etf(hyg)
    tip_selection = selector.select_for_etf(tip)

    assert lqd_selection.asset_bucket == "Investment Grade Credit"
    assert lqd_selection.spread_proxy_series_id == "BAMLC0A0CM"

    assert hyg_selection.asset_bucket == "High Yield"
    assert hyg_selection.spread_proxy_series_id == "BAMLH0A0HYM2"

    assert tip_selection.spread_proxy_series_id is None


def test_risk_proxy_selector_classifies_short_duration_cash_like_bucket() -> None:
    selector = RiskProxySelector()
    sgov = ETF("SGOV", name="Treasury Bill ETF", asset_class="UST Short")

    selection = selector.select_for_etf(sgov)

    assert selection.asset_bucket == "Short Duration / Cash-like"
    assert selection.spread_proxy_series_id is None
