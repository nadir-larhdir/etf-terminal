import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        """No-op fallback when python-dotenv is not installed yet."""

        return False

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
ENV_DB_FILENAMES = {
    "prod": "market_data_prod.db",
    "uat": "market_data_uat.db",
}

load_dotenv(BASE_DIR / ".env")


def get_app_env() -> str:
    """Return the active application environment used for database selection."""

    raw_env = os.getenv("APP_ENV", "prod").strip().lower()
    return raw_env if raw_env in ENV_DB_FILENAMES else "prod"


APP_ENV = get_app_env()
DB_PATH = BASE_DIR / ENV_DB_FILENAMES[APP_ENV]
FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
FRED_BASE_URL = "https://api.stlouisfed.org/fred"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


_config = load_config()

"""Static default ticker universe loaded from the JSON configuration file."""
DEFAULT_TICKERS = _config["DEFAULT_TICKERS"]
"""Predefined lookback windows used by the dashboard controls."""
PERIOD_OPTIONS = _config["PERIOD_OPTIONS"]
