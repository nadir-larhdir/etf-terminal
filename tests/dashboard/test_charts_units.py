from __future__ import annotations

import pandas as pd

from dashboard.components import charts


def test_volume_chart_uses_rolling_30d_average(monkeypatch) -> None:
    captured = {}

    def fake_plotly_chart(fig, **kwargs):
        captured["fig"] = fig
        captured["kwargs"] = kwargs

    monkeypatch.setattr(charts.st, "plotly_chart", fake_plotly_chart)
    index = pd.bdate_range("2026-01-01", periods=35)
    history = pd.DataFrame(
        {
            "volume": list(range(1, 36)),
            "close": 100.0,
        },
        index=index,
    )

    charts.render_volume_chart(history, "TEST", index[-5].date(), index[-1].date())

    fig = captured["fig"]
    avg_trace = next(trace for trace in fig.data if trace.name == "30D Avg")
    expected = history["volume"].rolling(30, min_periods=1).mean().tail(5).tolist()

    assert list(avg_trace.y) == expected
