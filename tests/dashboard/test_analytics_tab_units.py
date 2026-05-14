from __future__ import annotations

from types import SimpleNamespace

from dashboard.tabs.analytics_tab import AnalyticsTab


def test_per_share_dv01_uses_dashboard_10000_share_convention() -> None:
    tab = AnalyticsTab(analytics_service=None)

    assert tab._format_dollar_per_million(0.024048) == "$240"
    assert tab._format_dollar_per_million(0.08) == "$800"


def test_per_share_cs01_uses_dashboard_10000_share_convention() -> None:
    tab = AnalyticsTab(analytics_service=None)

    assert tab._format_dollar_per_million(0.02) == "$200"


def test_current_read_uses_dashboard_10000_share_convention() -> None:
    tab = AnalyticsTab(analytics_service=None)
    analytics = SimpleNamespace(estimated_duration=3.0, dv01_per_share=0.024048)

    body = tab._current_read_body(
        SimpleNamespace(asset_class="High Yield", history=None),
        {"benchmark_index": "Test Benchmark"},
        {},
        analytics,
        "Provider",
        "metadata",
    )

    assert "$240 per $1MM" in body


def test_per_million_risk_colors_use_dashboard_10000_share_convention() -> None:
    tab = AnalyticsTab(analytics_service=None)

    assert tab._dv01_risk_color(0.024048) == "#D4A017"
    assert tab._cs01_risk_color(0.02) == "#D4A017"
