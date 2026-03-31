from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "market_data.db"

DEFAULT_TICKERS = {
    "LQD": {
        "name": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
        "asset_class": "IG Credit",
    },
    "HYG": {
        "name": "iShares iBoxx $ High Yield Corporate Bond ETF",
        "asset_class": "HY Credit",
    },
    "IEF": {
        "name": "iShares 7-10 Year Treasury Bond ETF",
        "asset_class": "UST 7-10Y",
    },
    "TLT": {
        "name": "iShares 20+ Year Treasury Bond ETF",
        "asset_class": "UST 20Y+",
    },
}

PERIOD_OPTIONS = {
    "5D": 5,
    "30D": 30,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
}
