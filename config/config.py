"""Application-wide configuration loaded once at startup from env vars and config.json."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

ENV_DB_FILENAMES = {
    "prod": "market_data_prod.db",
    "uat": "market_data_uat.db",
}
VALID_DATA_BACKENDS = {"local", "supabase"}

load_dotenv(BASE_DIR / ".env")


def get_app_env() -> str:
    """Return the validated APP_ENV value, defaulting to 'prod' on unrecognised input."""
    raw = os.getenv("APP_ENV", "prod").strip().lower()
    return raw if raw in ENV_DB_FILENAMES else "prod"


def load_config() -> dict:
    """Load and return the JSON configuration file as a plain dict."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


APP_ENV = get_app_env()
DB_SCHEMA = os.getenv("SUPABASE_SCHEMA", "public").strip() or "public"
DB_PATH = BASE_DIR / ENV_DB_FILENAMES[APP_ENV]

# Support both DATABASE_URL (legacy) and SUPABASE_DB_URL.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or os.getenv("SUPABASE_DB_URL", "").strip()
SUPABASE_DB_URL = DATABASE_URL

_default_backend = "supabase" if DATABASE_URL else "local"
DATA_BACKEND = os.getenv("DATA_BACKEND", _default_backend).strip().lower()
if DATA_BACKEND not in VALID_DATA_BACKENDS:
    DATA_BACKEND = _default_backend

FMP_API_KEY = os.getenv("FMP_API_KEY", "").strip()
FMP_BASE_URL = "https://financialmodelingprep.com/stable"
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

_config = load_config()
DEFAULT_TICKERS: dict[str, dict[str, str]] = _config["DEFAULT_TICKERS"]
PERIOD_OPTIONS: dict[str, int] = _config["PERIOD_OPTIONS"]
MACRO_SERIES_REGISTRY: dict[str, dict[str, str]] = _config["MACRO_SERIES_REGISTRY"]
NEWS_FEEDS: dict[str, dict[str, str]] = _config["NEWS_FEEDS"]
