"""FINRA market, bond, and bond-analytics client."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import requests
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

from config import FINRA_CLIENT_ID, FINRA_CLIENT_SECRET

_DYNAREP_PUBLIC = (
    "https://services-dynarep.ddwa.finra.org/public/reporting/v2/data/group/FixedIncomeMarket/name"
)
_FINRA_API_BASE = "https://api.finra.org/data/group"
_FINRA_TOKEN_URL = (
    "https://ews.fip.finra.org/fip/rest/ews/oauth2/access_token?grant_type=client_credentials"
)
_FINRA_HOME = "https://www.finra.org/finra-data/fixed-income/bond"
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/26.3.1 Safari/605.1.15"
)
_SESSION_TTL = 25 * 60  # 25 minutes
_SECURITY_DATASETS = {
    "corporate": {
        "securities": "CorporateAndAgencySecurities",
        "price_yield": "EndOfDayPriceYield",
        "trade_history": "CorporateAndAgencyTradeHistory",
    },
    "treasury": {
        "securities": "TreasurySecurities",
        "price_yield": "TreasuryEndOfDayPriceYield",
        "trade_history": "TreasuryTradeActivity",
    },
}


@dataclass
class BondInfo:
    cusip: str
    symbol: str
    issuer: str
    coupon: float
    maturity: date
    rating_moodys: str
    rating_sp: str
    price: float
    ytm: float
    macaulay_duration: float = 0.0
    modified_duration: float = 0.0
    dv01: float = 0.0
    years_to_maturity: float = 0.0
    implied_ytm_pct: float = 0.0
    curve_pv: float = 0.0
    credit_spread_bps: float = 0.0
    benchmark_tenor: float = 0.0
    benchmark_yield_pct: float = 0.0


class USTCurve:
    _TICKERS = {
        0.25: "DGS3MO",
        0.5: "DGS6MO",
        1: "DGS1",
        2: "DGS2",
        3: "DGS3",
        5: "DGS5",
        7: "DGS7",
        10: "DGS10",
        20: "DGS20",
        30: "DGS30",
    }
    _cache: dict[str, CubicSpline] = {}

    @classmethod
    def benchmark_tenor(cls, years_to_maturity: float) -> float:
        """Return the closest available Treasury tenor for a bond maturity."""
        tenors = sorted(cls._TICKERS)
        years = max(float(years_to_maturity), tenors[0])
        return min(tenors, key=lambda tenor: (abs(tenor - years), tenor))

    @classmethod
    def get(cls, trade_date: str) -> CubicSpline:
        import pandas_datareader.data as pdr

        if trade_date in cls._cache:
            return cls._cache[trade_date]
        start = (datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
        rates = {}
        for maturity, ticker in cls._TICKERS.items():
            frame = pdr.DataReader(ticker, "fred", start, trade_date)
            rates[maturity] = frame.dropna().iloc[-1, 0] / 100.0
        curve = CubicSpline(list(rates.keys()), list(rates.values()))
        cls._cache[trade_date] = curve
        return curve


class BondAnalytics:
    @staticmethod
    def _cash_flows(
        coupon_rate: float,
        maturity: date,
        face: float = 100.0,
        frequency: int = 2,
    ) -> tuple[list[float], list[float], float]:
        today = date.today()
        years = (maturity - today).days / 365.25
        periods = max(int(years * frequency), 1)
        c = face * (coupon_rate / 100.0) / frequency
        cfs = [c] * periods
        cfs[-1] += face
        times = [(i + 1) / frequency for i in range(periods)]
        return cfs, times, years

    @staticmethod
    def ytm_from_price(
        price: float, coupon_rate: float, maturity: date, face: float = 100.0, frequency: int = 2
    ) -> float | None:
        cfs, _, years = BondAnalytics._cash_flows(coupon_rate, maturity, face, frequency)
        if years <= 0:
            return None

        def pv_diff(y: float) -> float:
            r = y / frequency
            return sum(cf / (1 + r) ** (i + 1) for i, cf in enumerate(cfs)) - price

        try:
            return float(brentq(pv_diff, 1e-4, 10.0))
        except (ValueError, RuntimeError):
            return None

    @staticmethod
    def duration_from_ytm(
        price: float,
        coupon_rate: float,
        ytm: float,
        maturity: date,
        face: float = 100.0,
        frequency: int = 2,
    ) -> dict[str, float]:
        cfs, times, years = BondAnalytics._cash_flows(coupon_rate, maturity, face, frequency)
        r = ytm / frequency
        pv_cfs = [cf / (1 + r) ** (i + 1) for i, cf in enumerate(cfs)]
        total_pv = sum(pv_cfs)
        mac = sum(t * pv / total_pv for t, pv in zip(times, pv_cfs, strict=False))
        mod = mac / (1 + r)
        return {
            "macaulay_duration": round(mac, 4),
            "modified_duration": round(mod, 4),
            "dv01": round(mod * price / 10000, 6),
            "years_to_maturity": round(years, 2),
        }

    @staticmethod
    def duration_from_curve(
        price: float,
        coupon_rate: float,
        maturity: date,
        curve: CubicSpline,
        face: float = 100.0,
        frequency: int = 2,
    ) -> dict[str, float]:
        cfs, times, years = BondAnalytics._cash_flows(coupon_rate, maturity, face, frequency)
        pv_cfs = [
            cf / (1 + float(curve(min(t, 30)))) ** t for t, cf in zip(times, cfs, strict=False)
        ]
        total_pv = sum(pv_cfs)
        mac = sum(t * pv / total_pv for t, pv in zip(times, pv_cfs, strict=False))
        mod = mac / (1 + float(curve(2)) / frequency)

        def pv_diff(y: float) -> float:
            r = y / frequency
            return sum(cf / (1 + r) ** (i + 1) for i, cf in enumerate(cfs)) - price

        try:
            implied_ytm = brentq(pv_diff, 1e-4, 0.5) * 100
        except Exception:
            implied_ytm = float("nan")
        return {
            "macaulay_duration": round(mac, 4),
            "modified_duration": round(mod, 4),
            "dv01": round(mod * price / 10000, 6),
            "years_to_maturity": round(years, 2),
            "implied_ytm_pct": round(implied_ytm, 4),
            "curve_pv": round(total_pv, 4),
        }


class FINRAClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        *,
        session: Any = None,
        browser_headless: bool = True,
    ) -> None:
        self.client_id = (client_id or FINRA_CLIENT_ID).strip()
        self.client_secret = (client_secret or FINRA_CLIENT_SECRET).strip()
        self.session = session or requests.Session()
        self.browser_headless = browser_headless
        self._api_token: str | None = None
        self._api_token_expiry = 0.0
        self._hidden_session: Any = None
        self._xsrf_token: str | None = None
        self._session_last_refresh = 0.0

    # ── Official API ───────────────────────────────────────────────────────────

    def get_treasury_monthly_aggregates(self, limit: int = 50) -> pd.DataFrame:
        return pd.DataFrame(
            self._api_post("fixedIncomeMarket", "treasuryMonthlyAggregates", {"limit": limit})
        )

    def get_treasury_daily_aggregates(self, limit: int = 50) -> pd.DataFrame:
        return pd.DataFrame(
            self._api_post("fixedIncomeMarket", "treasuryDailyAggregates", {"limit": limit})
        )

    def get_corporate_market_breadth(self, limit: int = 50) -> pd.DataFrame:
        return pd.DataFrame(
            self._api_post("fixedIncomeMarket", "corporateMarketBreadth", {"limit": limit})
        )

    def get_corporate_144a_breadth(self, limit: int = 50) -> pd.DataFrame:
        return pd.DataFrame(
            self._api_post("fixedIncomeMarket", "corporate144aMarketBreadth", {"limit": limit})
        )

    def get_short_sale_volume(self, ticker: str, limit: int = 60) -> pd.DataFrame:
        frame = pd.DataFrame(
            self._api_post(
                "otcMarket",
                "regShoDaily",
                {
                    "compareFilters": [
                        {
                            "fieldName": "securitiesInformationProcessorSymbolIdentifier",
                            "compareType": "EQUAL",
                            "fieldValue": ticker,
                        }
                    ],
                    "limit": limit,
                },
            )
        )
        if frame.empty:
            return frame
        frame["tradeReportDate"] = pd.to_datetime(frame["tradeReportDate"])
        daily = (
            frame.groupby("tradeReportDate", as_index=False)
            .agg(totalVolume=("totalParQuantity", "sum"), shortVolume=("shortParQuantity", "sum"))
            .sort_values("tradeReportDate")
            .reset_index(drop=True)
        )
        daily["shortVolumeRatio"] = daily["shortVolume"] / daily["totalVolume"]
        return daily

    def get_short_interest(self, ticker: str, limit: int = 24) -> pd.DataFrame:
        return pd.DataFrame(
            self._api_post(
                "otcMarket",
                "consolidatedShortInterest",
                {
                    "compareFilters": [
                        {"fieldName": "symbolCode", "compareType": "EQUAL", "fieldValue": ticker}
                    ],
                    "limit": limit,
                },
            )
        )

    def get_weekly_summary(self, ticker: str, limit: int = 52) -> pd.DataFrame:
        frame = pd.DataFrame(
            self._api_post(
                "otcMarket",
                "weeklySummary",
                {
                    "compareFilters": [
                        {
                            "fieldName": "issueSymbolIdentifier",
                            "compareType": "EQUAL",
                            "fieldValue": ticker,
                        },
                        {
                            "fieldName": "summaryTypeCode",
                            "compareType": "EQUAL",
                            "fieldValue": "ATS_W_SMBL",
                        },
                    ],
                    "limit": limit,
                },
            )
        )
        return (
            frame.sort_values("weekStartDate").reset_index(drop=True) if not frame.empty else frame
        )

    # ── Session management ─────────────────────────────────────────────────────

    async def refresh_session(self) -> None:
        """Acquire XSRF token via headless browser (invisible, bypasses Cloudflare)."""
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.browser_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--window-size=1280,800",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent=_USER_AGENT,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
            )
            # Hide automation signals
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver',  {get: () => undefined});
                Object.defineProperty(navigator, 'plugins',    {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages',  {get: () => ['en-US', 'en']});
            """)
            page = await context.new_page()

            # Navigate to FINRA bond page — sets XSRF-TOKEN after JS runs
            try:
                await page.goto(_FINRA_HOME, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass  # partial load is fine — we just need cookies

            # Poll for XSRF-TOKEN (set by JS, takes ~1-3s)
            xsrf = None
            cookies = []
            for _ in range(60):  # up to 30s
                cookies = await context.cookies()
                xsrf = next((c["value"] for c in cookies if c["name"] == "XSRF-TOKEN"), None)
                if xsrf:
                    break
                await page.wait_for_timeout(500)

            await browser.close()

        if not xsrf:
            raise RuntimeError(
                f"XSRF-TOKEN not found. Cookies present: {[c['name'] for c in cookies]}"
            )

        session = requests.Session()
        for c in cookies:
            session.cookies.set(c["name"], c["value"])

        self._hidden_session = session
        self._xsrf_token = xsrf
        self._session_last_refresh = time.time()

    def refresh_session_sync(self) -> None:
        """Sync wrapper — works both in Jupyter and regular scripts."""
        try:
            import nest_asyncio

            nest_asyncio.apply()
        except ImportError:
            pass
        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.refresh_session())
        except RuntimeError:
            asyncio.run(self.refresh_session())

    async def _ensure_fresh_session(self) -> None:
        if (
            self._hidden_session is None
            or self._xsrf_token is None
            or time.time() - self._session_last_refresh > _SESSION_TTL
        ):
            await self.refresh_session()

    # ── Hidden endpoint: Bond data ─────────────────────────────────────────────

    async def get_bond_details(
        self, cusip: str, *, security_type: str = "corporate"
    ) -> dict[str, Any]:
        await self._ensure_fresh_session()
        rows = self._hidden_post(
            self._security_dataset(security_type, "securities"),
            {
                "fields": [
                    "cusip",
                    "issueSymbolIdentifier",
                    "issuerName",
                    "couponRate",
                    "maturityDate",
                    "lastSalePrice",
                    "lastSaleYield",
                    "moodysRating",
                    "standardAndPoorsRating",
                ],
                "orFilters": [{"compareFilters": self._instrument_filters(cusip)}],
                "offset": 0,
                "limit": 1,
            },
        )
        return rows[0] if rows else {}

    async def get_treasury_details(self, cusip: str) -> dict[str, Any]:
        return await self.get_bond_details(cusip, security_type="treasury")

    async def get_price_yield(
        self, cusip: str, trade_date: str, *, security_type: str = "corporate"
    ) -> dict[str, float | None]:
        await self._ensure_fresh_session()
        rows = self._hidden_post(
            self._security_dataset(security_type, "price_yield"),
            {
                "fields": ["cusip", "lastSalePrice", "lastSaleYield", "tradeDate"],
                "orFilters": [{"compareFilters": self._instrument_filters(cusip)}],
                "dateRangeFilters": [self._date_range("tradeDate", trade_date, trade_date)],
                "sortFields": ["tradeDate"],
                "offset": 0,
                "limit": 1,
            },
        )
        if not rows:
            return {"price": None, "ytm": None}
        return {"price": rows[0].get("lastSalePrice"), "ytm": rows[0].get("lastSaleYield")}

    async def get_price_yield_history(
        self,
        cusip: str,
        start: str = "2021-01-01",
        end: str | None = None,
        *,
        security_type: str = "corporate",
    ) -> pd.DataFrame:
        await self._ensure_fresh_session()
        end = end or date.today().isoformat()
        frame = pd.DataFrame(
            self._hidden_post(
                self._security_dataset(security_type, "price_yield"),
                {
                    "fields": ["cusip", "lastSalePrice", "lastSaleYield", "tradeDate"],
                    "orFilters": [{"compareFilters": self._instrument_filters(cusip)}],
                    "dateRangeFilters": [self._date_range("tradeDate", start, end)],
                    "sortFields": ["tradeDate"],
                    "offset": 0,
                    "limit": 5000,
                },
            )
        )
        if frame.empty:
            return frame
        frame["tradeDate"] = pd.to_datetime(frame["tradeDate"])
        frame["lastSalePrice"] = pd.to_numeric(frame["lastSalePrice"], errors="coerce")
        frame["lastSaleYield"] = pd.to_numeric(frame["lastSaleYield"], errors="coerce")
        return (
            frame[frame["lastSalePrice"] > 0]
            .dropna(subset=["lastSaleYield"])
            .sort_values("tradeDate")
            .reset_index(drop=True)
        )

    async def get_trade_history(
        self,
        symbol: str,
        start: str,
        end: str | None = None,
        limit: int = 5000,
        *,
        security_type: str = "corporate",
    ) -> pd.DataFrame:
        """
        Trade history for a FINRA issueSymbolIdentifier.

        Corporate/agency returns tick-by-tick TRACE rows. Treasury uses FINRA's
        TreasuryTradeActivity dataset, which is activity-style rows by trade date/time.
        """
        await self._ensure_fresh_session()
        end = end or date.today().isoformat()
        if security_type.lower() == "treasury":
            return self._normalize_treasury_trade_activity(
                self._hidden_post(
                    self._security_dataset("treasury", "trade_history"),
                    self._treasury_trade_activity_payload(symbol, start, end, limit),
                )
            )

        frame = pd.DataFrame(
            self._hidden_post(
                self._security_dataset(security_type, "trade_history"),
                {
                    "fields": [
                        "issueSymbolIdentifier",
                        "issuerName",
                        "tradeExecutionDate",
                        "reportedTradeVolume",
                        "lastSalePrice",
                        "lastSaleYield",
                        "tradeExecutionTime",
                        "reportingPartySideCode",
                    ],
                    "compareFilters": [
                        {
                            "fieldName": "issueSymbolIdentifier",
                            "compareType": "EQUAL",
                            "fieldValue": symbol,
                        }
                    ],
                    "dateRangeFilters": [
                        {"fieldName": "tradeExecutionDate", "startDate": start, "endDate": end}
                    ],
                    "domainFilters": [],
                    "multiFieldMatchFilters": [],
                    "orFilters": [],
                    "aggregationFilter": None,
                    "sortFields": ["-tradeExecutionDate", "-tradeExecutionTime"],
                    "limit": limit,
                    "offset": 0,
                    "delimiter": None,
                    "quoteValues": False,
                },
            )
        )
        if frame.empty:
            return frame
        frame["tradeExecutionTime"] = pd.to_datetime(
            frame["tradeExecutionDate"] + " " + frame["tradeExecutionTime"], errors="coerce"
        )
        for col in ["lastSalePrice", "lastSaleYield", "reportedTradeVolume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame.sort_values("tradeExecutionTime").reset_index(drop=True)

    def _treasury_trade_activity_payload(
        self, symbol: str, start: str, end: str, limit: int
    ) -> dict[str, Any]:
        """Return FINRA TreasuryTradeActivity request payload."""
        return {
            "fields": [
                "issueSymbolIdentifier",
                "benchmarkTermCode",
                "tradeDate",
                "tradeTime",
                "reportedTradeVolume",
                "priceType",
                "lastSalePrice",
                "lastSaleYield",
                "tradeStatus",
                "reportingSideCode",
                "contraPartyTypeCode",
                "productSubTypeCode",
            ],
            "dateRangeFilters": [self._date_range("tradeDate", start, end)],
            "domainFilters": [],
            "compareFilters": [
                {
                    "fieldName": "issueSymbolIdentifier",
                    "compareType": "EQUAL",
                    "fieldValue": symbol,
                }
            ],
            "multiFieldMatchFilters": [],
            "orFilters": [],
            "aggregationFilter": None,
            "sortFields": ["-tradeDate", "-tradeTime"],
            "limit": limit,
            "offset": 0,
            "delimiter": None,
            "quoteValues": False,
        }

    def _normalize_treasury_trade_activity(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        """Return cleaned TreasuryTradeActivity rows."""
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame["tradeExecutionTime"] = pd.to_datetime(
            frame["tradeDate"] + " " + frame["tradeTime"], errors="coerce"
        )
        for col in ["lastSalePrice", "lastSaleYield", "reportedTradeVolume"]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame.sort_values("tradeExecutionTime").reset_index(drop=True)

    async def search_bond_by_name(
        self, issuer_name: str, coupon: float, maturity: str
    ) -> dict[str, Any] | None:
        await self._ensure_fresh_session()
        rows = self._hidden_post(
            "CorporateAndAgencySecurities",
            {
                "fields": [
                    "cusip",
                    "issueSymbolIdentifier",
                    "issuerName",
                    "couponRate",
                    "maturityDate",
                    "lastSalePrice",
                    "lastSaleYield",
                ],
                "compareFilters": [
                    {"fieldName": "couponRate", "compareType": "EQUAL", "fieldValue": str(coupon)},
                    {
                        "fieldName": "issuerName",
                        "compareType": "BEGINS_WITH",
                        "fieldValue": issuer_name.split()[0],
                    },
                    {"fieldName": "maturityDate", "compareType": "EQUAL", "fieldValue": maturity},
                ],
                "offset": 0,
                "limit": 1,
            },
        )
        return rows[0] if rows else None

    async def get_bond_analytics(
        self,
        cusip: str,
        trade_date: str,
        use_curve: bool = True,
        *,
        security_type: str = "corporate",
    ) -> BondInfo:
        await self._ensure_fresh_session()
        details = await self.get_bond_details(cusip, security_type=security_type)
        price_yield = await self.get_price_yield(cusip, trade_date, security_type=security_type)

        price, ytm = price_yield["price"], price_yield["ytm"]
        # FINRA reports no price and no yield for a CUSIP that did not trade that day;
        # both are required downstream, so treat either being absent as no data.
        if not details or price is None or ytm is None:
            raise ValueError(f"No traded price or yield for CUSIP {cusip} on {trade_date}")

        coupon = details["couponRate"]
        maturity = datetime.strptime(details["maturityDate"], "%Y-%m-%d").date()

        if use_curve:
            curve = USTCurve.get(trade_date)
            duration = BondAnalytics.duration_from_curve(price, coupon, maturity, curve)
            benchmark_tenor = USTCurve.benchmark_tenor(duration["years_to_maturity"])
            benchmark_yield_pct = float(curve(benchmark_tenor)) * 100
            credit_spread = (duration["implied_ytm_pct"] - benchmark_yield_pct) * 100
        else:
            duration = BondAnalytics.duration_from_ytm(price, coupon, ytm / 100, maturity)
            credit_spread = float("nan")
            benchmark_tenor = 0.0
            benchmark_yield_pct = float("nan")

        return BondInfo(
            cusip=cusip,
            symbol=details.get("issueSymbolIdentifier", ""),
            issuer=details.get("issuerName", ""),
            coupon=coupon,
            maturity=maturity,
            rating_moodys=details.get("moodysRating", ""),
            rating_sp=details.get("standardAndPoorsRating", ""),
            price=price,
            ytm=ytm,
            credit_spread_bps=round(credit_spread, 2),
            benchmark_tenor=benchmark_tenor,
            benchmark_yield_pct=round(benchmark_yield_pct, 4),
            **duration,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _api_post(self, group: str, dataset: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        r = self.session.post(
            f"{_FINRA_API_BASE}/{group}/name/{dataset}",
            headers=self._api_headers(),
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        return r.json() if r.text.strip() else []

    def _refresh_api_token(self) -> None:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("FINRA_CLIENT_ID and FINRA_CLIENT_SECRET are required")
        r = self.session.post(
            _FINRA_TOKEN_URL, auth=(self.client_id, self.client_secret), timeout=10
        )
        r.raise_for_status()
        self._api_token = r.json()["access_token"]
        self._api_token_expiry = time.time() + 3300

    def _api_headers(self) -> dict[str, str]:
        if time.time() >= self._api_token_expiry:
            self._refresh_api_token()
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _session_headers(self) -> dict[str, str]:
        if not self._xsrf_token:
            raise RuntimeError("Call refresh_session() first.")
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://www.finra.org",
            "Referer": "https://www.finra.org/",
            "User-Agent": _USER_AGENT,
            "X-XSRF-TOKEN": self._xsrf_token,
        }

    def _hidden_post(self, endpoint: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if self._hidden_session is None:
            raise RuntimeError("Call refresh_session() first.")
        r = self._hidden_session.post(
            f"{_DYNAREP_PUBLIC}/{endpoint}",
            headers=self._session_headers(),
            json=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        raw = data.get("returnBody", {}).get("data", "[]")
        rows: list[dict[str, Any]] = json.loads(raw) if isinstance(raw, str) else raw
        return rows

    def _security_dataset(self, security_type: str, dataset: str) -> str:
        try:
            return _SECURITY_DATASETS[security_type.lower()][dataset]
        except KeyError as exc:
            valid = ", ".join(sorted(_SECURITY_DATASETS))
            raise ValueError(
                f"Unknown FINRA security_type '{security_type}'. Use: {valid}"
            ) from exc

    def _instrument_filters(self, value: str) -> list[dict[str, str]]:
        return [
            {"fieldName": "cusip", "compareType": "EQUAL", "fieldValue": value},
            {"fieldName": "issueSymbolIdentifier", "compareType": "EQUAL", "fieldValue": value},
        ]

    def _date_range(self, field_name: str, start: str, end: str) -> dict[str, str]:
        return {
            "fieldName": field_name,
            "startDate": f"{start} 00:00:00.000",
            "endDate": f"{end} 23:59:59.999",
        }


FINRA = FINRAClient
