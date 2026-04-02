import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "market_data.db"
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


_config = load_config()

"""Static default ticker universe loaded from the JSON configuration file."""
DEFAULT_TICKERS = _config["DEFAULT_TICKERS"]
"""Predefined lookback windows used by the dashboard controls."""
PERIOD_OPTIONS = _config["PERIOD_OPTIONS"]
