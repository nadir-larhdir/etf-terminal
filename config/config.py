import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
ENV_DB_FILENAMES = {
    "prod": "market_data_prod.db",
    "uat": "market_data_uat.db",
}


def get_app_env() -> str:
    """Return the active application environment used for database selection."""

    raw_env = os.getenv("APP_ENV", "prod").strip().lower()
    return raw_env if raw_env in ENV_DB_FILENAMES else "prod"


APP_ENV = get_app_env()
DB_PATH = BASE_DIR / ENV_DB_FILENAMES[APP_ENV]


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


_config = load_config()

"""Static default ticker universe loaded from the JSON configuration file."""
DEFAULT_TICKERS = _config["DEFAULT_TICKERS"]
"""Predefined lookback windows used by the dashboard controls."""
PERIOD_OPTIONS = _config["PERIOD_OPTIONS"]
