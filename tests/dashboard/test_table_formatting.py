from __future__ import annotations

import pandas as pd

from dashboard.styles.table_styles import DashboardTable


def test_screener_formats_spread_dev_as_percent() -> None:
    table = DashboardTable()
    frame = pd.DataFrame(
        {
            "PAIR": ["LQD/IEF"],
            "SPREAD DEV": [0.42],
            "FWD 20D RET": [-0.13],
            "REGIME": ["RICH"],
        }
    )

    formatted = table.format_screener(frame)

    assert formatted.loc[0, "SPREAD DEV"] == "+0.42%"
    assert formatted.loc[0, "FWD 20D RET"] == "-0.13%"
