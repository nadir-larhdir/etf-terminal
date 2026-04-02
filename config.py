import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "market_data.db"
CONFIG_PATH = BASE_DIR / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


_config = load_config()

DEFAULT_TICKERS = _config["DEFAULT_TICKERS"]
PERIOD_OPTIONS = _config["PERIOD_OPTIONS"]