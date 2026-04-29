from __future__ import annotations

from io import StringIO

import numpy as np
import pandas as pd
import requests
from sqlalchemy import text

from db.sql import qualified_table

ISHARES_ETFS = {
    "SLQD": ("258098", "ishares-iboxx-investment-grade-corporate-bond-etf"),
    "SHY": ("239452", "ishares-1-3-year-treasury-bond-etf"),
    "IEI": ("239455", "ishares-3-7-year-treasury-bond-etf"),
    "IEF": ("239456", "ishares-7-10-year-treasury-bond-etf"),
    "TLT": ("239454", "ishares-20-year-treasury-bond-etf"),
    "GOVT": ("239458", "ishares-us-treasury-bond-etf"),
    "MUB": ("239766", "ishares-national-amtfree-muni-bond-etf"),
    "MBB": ("239465", "ishares-mbs-etf"),
    "LQD": ("239566", "ishares-iboxx-investment-grade-corporate-bond-etf"),
    "HYG": ("239565", "ishares-iboxx-high-yield-corporate-bond-etf"),
    "SHYG": ("258100", "ishares-0-5-year-high-yield-corporate-bond-etf"),
    "IGSB": ("239451", "ishares-1-5-year-investment-grade-corporate-bond-etf"),
    "EMB": ("239572", "ishares-jp-morgan-usd-emerging-markets-bond-etf"),
    "IUSB": ("264615", "ishares-core-total-usd-bond-market-etf"),
    "STIP": ("239450", "ishares-05-year-tips-bond-etf"),
    "TIP": ("239467", "ishares-tips-bond-etf"),
    "AGG": ("239458", "ishares-core-us-aggregate-bond-etf"),
    "FLOT": ("239534", "ishares-floating-rate-bond-etf"),
}

PROXY_MAP = {
    "BND": "AGG",
    "BSV": "IGSB",
    "SPSB": "SLQD",
    "VCSH": "IGSB",
    "VGSH": "SHY",
    "FLRN": "FLOT",
    "VTEB": "MUB",
    "JNK": "HYG",
    "SJNK": "SHYG",
    "VWOB": "EMB",
    "VMBS": "MBB",
}

CURVE_REGRESSION_TICKERS = {"HYD", "VCIT", "EDV", "PCY"}
TREASURY_TENORS = ["DGS3MO", "DGS6MO", "DGS1", "DGS2", "DGS5", "DGS10", "DGS20", "DGS30"]
ISHARES_HOLDINGS_URL = (
    "https://www.ishares.com/us/products/{pid}/{slug}/1467271812596.ajax"
    "?fileType=csv&fileName={ticker}_holdings&dataType=fund"
)


def issuer_from_long_name(long_name: str | None) -> str | None:
    if not long_name:
        return None
    tokens = str(long_name).strip().split()
    return tokens[0] if tokens else None


class SecurityDurationEstimator:
    def __init__(self, engine, session: requests.Session | None = None):
        self.engine = engine
        self.session = session or requests.Session()
        self._duration_cache: dict[str, float | None] = {}

    def estimate_duration(self, ticker: str) -> float | None:
        normalized = str(ticker).strip().upper()
        if not normalized:
            return None
        if normalized in self._duration_cache:
            return self._duration_cache[normalized]

        if normalized in ISHARES_ETFS:
            value = self._fetch_ishares_duration(normalized)
        elif normalized in PROXY_MAP:
            value = self._estimate_proxy_duration(normalized, PROXY_MAP[normalized])
        elif normalized in CURVE_REGRESSION_TICKERS:
            value = self._estimate_curve_duration(normalized)
        else:
            value = None

        rounded = round(float(value), 1) if value is not None else None
        self._duration_cache[normalized] = rounded
        return rounded

    def _fetch_ishares_duration(self, ticker: str) -> float | None:
        pid, slug = ISHARES_ETFS[ticker]
        url = ISHARES_HOLDINGS_URL.format(pid=pid, slug=slug, ticker=ticker)
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        frame = pd.read_csv(StringIO(response.text), skiprows=9, header=0)
        if "Duration" not in frame.columns or "Weight (%)" not in frame.columns:
            return None

        frame["Duration"] = pd.to_numeric(frame["Duration"], errors="coerce")
        frame["Weight (%)"] = pd.to_numeric(frame["Weight (%)"], errors="coerce")
        frame = frame.dropna(subset=["Duration", "Weight (%)"])
        if frame.empty:
            return None

        total_weight = float(frame["Weight (%)"].sum())
        if total_weight == 0:
            return None

        return float(frame["Duration"] @ frame["Weight (%)"] / total_weight)

    def _estimate_proxy_duration(self, ticker: str, proxy_ticker: str) -> float | None:
        proxy_duration = self.estimate_duration(proxy_ticker)
        if proxy_duration is None:
            return None

        beta = self._log_return_beta(ticker, proxy_ticker)
        if beta is None:
            return None

        return float(beta * proxy_duration)

    def _estimate_curve_duration(self, ticker: str) -> float | None:
        prices = self._load_price_history([ticker])
        rates = self._load_curve_history()
        if prices.empty or rates.empty:
            return None

        price_wide = prices.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        if ticker not in price_wide.columns:
            return None

        log_returns = np.log(price_wide).diff()
        curve = rates.pivot(index="date", columns="series_id", values="value").sort_index()

        change_columns: list[str] = []
        for tenor in TREASURY_TENORS:
            if tenor not in curve.columns:
                continue
            column = f"{tenor}_chg_bp"
            curve[column] = curve[tenor].diff() * 100.0
            change_columns.append(column)

        if not change_columns:
            return None

        frame = log_returns[[ticker]].join(curve[change_columns], how="inner").dropna()
        if frame.empty:
            return None

        y = frame[ticker].to_numpy()
        x = frame[change_columns].to_numpy()
        design = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        coefficients = pd.Series(beta[1:], index=change_columns)
        return float(-coefficients.sum() * 10_000)

    def _log_return_beta(self, left_ticker: str, right_ticker: str) -> float | None:
        prices = self._load_price_history([left_ticker, right_ticker])
        if prices.empty:
            return None

        price_wide = prices.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        required = {left_ticker, right_ticker}
        if not required.issubset(set(price_wide.columns)):
            return None

        log_returns = np.log(price_wide).diff().dropna()
        frame = log_returns[[left_ticker, right_ticker]].dropna()
        if frame.empty:
            return None

        y = frame[left_ticker].to_numpy()
        x = frame[[right_ticker]].to_numpy()
        design = np.column_stack([np.ones(len(x)), x])
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        return float(beta[1])

    def _load_price_history(self, tickers: list[str]) -> pd.DataFrame:
        placeholders = ", ".join(f":ticker_{idx}" for idx in range(len(tickers)))
        params = {f"ticker_{idx}": ticker for idx, ticker in enumerate(tickers)}
        query = text(f"""
            SELECT ticker, date, adj_close
            FROM {qualified_table(self.engine, 'price_history')}
            WHERE ticker IN ({placeholders})
            ORDER BY date, ticker
            """)
        with self.engine.connect() as conn:
            frame = pd.read_sql(query, conn, params=params)
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"])
        return frame

    def _load_curve_history(self) -> pd.DataFrame:
        placeholders = ", ".join(f":series_{idx}" for idx in range(len(TREASURY_TENORS)))
        params = {f"series_{idx}": series_id for idx, series_id in enumerate(TREASURY_TENORS)}
        query = text(f"""
            SELECT series_id, date, value
            FROM {qualified_table(self.engine, 'macro_data')}
            WHERE series_id IN ({placeholders})
            ORDER BY date, series_id
            """)
        with self.engine.connect() as conn:
            frame = pd.read_sql(query, conn, params=params)
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"])
        return frame
