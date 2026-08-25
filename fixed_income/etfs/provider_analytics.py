from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

ISHARES_FUNDS = {
    "AGG": ("239458", "ishares-core-us-aggregate-bond-etf"),
    "EMB": ("239572", "ishares-jp-morgan-usd-emerging-markets-bond-etf"),
    "FLOT": ("239534", "ishares-floating-rate-bond-etf"),
    "GOVT": ("239468", "ishares-us-treasury-bond-etf"),
    "HYG": ("239565", "ishares-iboxx-high-yield-corporate-bond-etf"),
    "IEF": ("239456", "ishares-7-10-year-treasury-bond-etf"),
    "IEI": ("239455", "ishares-3-7-year-treasury-bond-etf"),
    "IGIB": ("239459", "ishares-intermediate-term-corporate-bond-etf"),
    "IGLB": ("239460", "ishares-10-year-investment-grade-corporate-bond-etf"),
    "IGSB": ("239451", "ishares-short-term-corporate-bond-etf"),
    "IUSB": ("264615", "ishares-core-total-usd-bond-market-etf"),
    "LQD": ("239566", "ishares-iboxx-investment-grade-corporate-bond-etf"),
    "MBB": ("239465", "ishares-mbs-etf"),
    "MUB": ("239766", "ishares-national-muni-bond-etf"),
    "SHY": ("239452", "ishares-1-3-year-treasury-bond-etf"),
    "SHYG": ("258100", "ishares-0-5-year-high-yield-corporate-bond-etf"),
    "SLQD": ("258098", "ishares-05-year-investment-grade-corporate-bond-etf"),
    "STIP": ("239450", "ishares-0-5-year-tips-bond-etf"),
    "TIP": ("239467", "ishares-tips-bond-etf"),
    "TLT": ("239454", "ishares-20-year-treasury-bond-etf"),
}

VANGUARD_FUND_IDS = {
    "BND": "0928",
    "EDV": "0930",
    "VCIT": "3146",
    "VCLT": "3147",
    "VCSH": "3145",
    "VGIT": "3143",
    "VGLT": "3144",
    "VGSH": "3142",
    "VMBS": "3148",
    "VTEB": "4391",
    "VWOB": "3820",
}

SSGA_FUNDS = {
    "FLRN": "spdr-bloomberg-investment-grade-floating-rate-etf-flrn",
    "JNK": "spdr-bloomberg-high-yield-bond-etf-jnk",
    "SJNK": "spdr-bloomberg-short-term-high-yield-bond-etf-sjnk",
    "SPHY": "spdr-portfolio-high-yield-bond-etf-sphy",
    "SPAB": "spdr-portfolio-aggregate-bond-etf-spab",
    "SPIB": "spdr-portfolio-intermediate-term-corporate-bond-etf-spib",
    "SPSB": "spdr-portfolio-short-term-corporate-bond-etf-spsb",
    "SPTI": "spdr-portfolio-intermediate-term-treasury-etf-spti",
    "SPTL": "spdr-portfolio-long-term-treasury-etf-sptl",
}

# ticker → (cusip, page-slug)  slug needed for the new URL structure
INVESCO_FUNDS = {
    "PCY": ("46138E784", "invesco-emerging-markets-sovereign-debt-etf"),
}

PROVIDER_BY_TICKER = {
    **dict.fromkeys(ISHARES_FUNDS, "iShares"),
    **dict.fromkeys(VANGUARD_FUND_IDS, "Vanguard"),
    **dict.fromkeys(SSGA_FUNDS, "SPDR"),
    **dict.fromkeys(INVESCO_FUNDS, "Invesco"),
}

_INVESCO_PRODUCT_BASE = "https://www.invesco.com/us/en/financial-products/etfs"
_INVESCO_DNG_BASE = "https://dng-api.invesco.com"
_INVESCO_CHAR_LABEL_MAP = {
    "Effective duration": "effective_duration",
    "Modified duration": "modified_duration",
    "Yield to maturity": "ytm",
    "Yield to worst": "ytw",
    "Years to maturity": "avg_maturity",
    "Weighted avg coupon": "avg_coupon",
}

_ISHARES_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Referer": "https://www.ishares.com/us/",
}
_ISHARES_PRODUCT_DATA_URL = (
    "https://www.blackrock.com/varnish-api/blk-one01-product-data"
    "/product-data/api/v2/get-product-data"
)
_SSGA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
}
_VANGUARD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
}


_RATING_BUCKETS = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D", "NR"]


@dataclass(frozen=True)
class ETFAnalytics:
    ticker: str
    provider: str
    effective_duration: float | None = None
    modified_duration: float | None = None
    ytm: float | None = None
    ytw: float | None = None
    oas: float | None = None
    convexity: float | None = None
    avg_maturity: float | None = None
    avg_coupon: float | None = None
    as_of: str | None = None

    @property
    def preferred_duration(self) -> float | None:
        return (
            self.effective_duration
            if self.effective_duration is not None
            else self.modified_duration
        )


def provider_for_ticker(ticker: str) -> str | None:
    return PROVIDER_BY_TICKER.get(ticker.strip().upper())


def _parse_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = re.search(r"[-+]?\d[\d,]*\.?\d*", str(value).replace(",", ""))
    return float(match.group().replace(",", "")) if match else None


def _parse_ishares_as_of(value: object) -> str | None:
    text = str(value or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"


def _ishares_product_data_params(product_id: str, component: str) -> dict[str, str]:
    return {
        "appSubType": "ISHARES",
        "appType": "PRODUCT_PAGE",
        "component": component,
        "locale": "en_US",
        "portfolioId": product_id,
        "targetSite": "us-ishares",
        "userType": "individual",
        "excludeContent": "true",
        "asOfDate": "",
        "includeConfig": "true",
    }


def _ishares_data_points(component: dict[str, Any]) -> dict[str, Any]:
    """Return the default iShares datapoints map for an API component payload."""
    data_points: dict[str, Any] = (
        component.get("containersByNameMap", {}).get("default", {}).get("dataPointsByNameMap", {})
    )
    return data_points


def _normalize_rating(value: str) -> str:
    """Collapse provider rating labels into broad buckets."""
    if not isinstance(value, str) or not value.strip():
        return "NR"

    rating = value.strip()
    lowered = rating.lower()
    if lowered in {"nr", "not rated"}:
        return "NR"
    if "cash" in lowered or "derivative" in lowered:
        return "CASH"
    if any(token in lowered for token in ("government", "treasury", "agency")):
        return "GOVT"

    rating = rating.split("/", 1)[0].strip()
    rating = re.sub(r"\s*rated\s*$", "", rating, flags=re.IGNORECASE).rstrip("uU")
    base = re.match(r"^[A-Za-z]+", rating)
    if not base:
        return "NR"

    moodys_to_sp = {
        "AAA": "AAA",
        "AA": "AA",
        "A": "A",
        "BAA": "BBB",
        "BA": "BB",
        "B": "B",
        "CAA": "CCC",
        "CA": "CC",
        "C": "C",
    }
    normalized = moodys_to_sp.get(base.group(0).upper(), base.group(0).upper())
    return normalized if normalized in _RATING_BUCKETS else "NR"


def _credit_quality_df(
    breakdown: dict[str, float], *, ticker: str, provider: str, normalize: bool
) -> pd.DataFrame:
    """Convert a raw rating breakdown dict to a standard dataframe."""
    if not breakdown:
        return pd.DataFrame(columns=["rating", "weight", "ticker", "provider"])

    rows = [{"rating": k, "weight": v} for k, v in breakdown.items()]
    df = pd.DataFrame(rows)
    if normalize:
        df["rating"] = df["rating"].map(_normalize_rating)
        df = pd.DataFrame(df.groupby("rating", as_index=False)["weight"].sum())
    df = df.sort_values("weight", ascending=False).reset_index(drop=True)
    df["ticker"] = ticker
    df["provider"] = provider
    return df


class ETFAnalyticsClient:
    """Fetch provider analytics for a supported fixed-income ETF ticker."""

    def __init__(self, ticker: str, session: requests.Session | None = None):
        self.ticker = ticker.strip().upper()
        self.session = session or requests.Session()
        provider = provider_for_ticker(self.ticker)
        if provider is None:
            raise ValueError(f"Unknown ticker '{ticker}'. Add it to the provider registry first.")
        self.provider = provider

    def get_analytics(self) -> ETFAnalytics:
        if self.provider == "iShares":
            return self._fetch_ishares()
        if self.provider == "Vanguard":
            return self._fetch_vanguard()
        if self.provider == "SPDR":
            return self._fetch_spdr()
        if self.provider == "Invesco":
            return self._fetch_invesco()
        raise ValueError(f"Unsupported ETF provider '{self.provider}' for {self.ticker}.")

    def get_credit_quality(self, *, normalize: bool = True) -> pd.DataFrame:
        """Fetch ETF credit-quality weights across providers."""
        if self.provider == "iShares":
            breakdown = self._fetch_ishares_credit_quality()
        elif self.provider == "Vanguard":
            breakdown = self._fetch_vanguard_credit_quality()
        elif self.provider == "SPDR":
            breakdown = self._fetch_spdr_credit_quality()
        elif self.provider == "Invesco":
            breakdown = self._fetch_invesco_credit_quality()
        else:
            breakdown = {}
        return _credit_quality_df(
            breakdown,
            ticker=self.ticker,
            provider=self.provider,
            normalize=normalize,
        )

    def _fetch_ishares(self) -> ETFAnalytics:
        component = self._fetch_ishares_component("fundamentalsAndRisk")
        data_points = _ishares_data_points(component)

        def value(name: str) -> float | None:
            return _parse_number(data_points.get(name, {}).get("value"))

        as_of = None
        for name in ("modelOad", "fxHedgedYield", "optionAdjustedSpread"):
            as_of = _parse_ishares_as_of(data_points.get(name, {}).get("asOfDate"))
            if as_of:
                break

        return ETFAnalytics(
            ticker=self.ticker,
            provider="iShares",
            effective_duration=value("modelOad"),
            ytm=value("fxHedgedYield"),
            oas=value("optionAdjustedSpread"),
            convexity=value("convexity"),
            avg_maturity=value("weightedAvgLife"),
            avg_coupon=value("weightedAvgCouponFi"),
            as_of=as_of,
        )

    def _fetch_ishares_component(self, component_name: str) -> dict[str, Any]:
        product_id, _ = ISHARES_FUNDS[self.ticker]
        response = self.session.get(
            _ISHARES_PRODUCT_DATA_URL,
            params=_ishares_product_data_params(product_id, component_name),
            headers=_ISHARES_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        component: dict[str, Any] | None = (
            response.json().get("componentsByNameMap", {}).get(component_name)
        )
        if not component:
            raise RuntimeError(f"[{self.ticker}] iShares {component_name} component not found")
        return component

    def _fetch_ishares_credit_quality(self) -> dict[str, float]:
        component = self._fetch_ishares_component("exposureBreakdowns")
        rating = component.get("containersByNameMap", {}).get("rating", {})
        data_points = rating.get("dataPointsByNameMap", {})
        labels = data_points.get("type", {}).get("value") or []
        weights = data_points.get("fund", {}).get("value") or []
        if not labels or not weights:
            return {}
        return {
            str(label).replace(" Rated", ""): float(weight or 0.0)
            for label, weight in zip(labels, weights, strict=False)
        }

    def _fetch_vanguard(self) -> ETFAnalytics:
        characteristics = self.session.get(
            f"https://investor.vanguard.com/vmf/api/{self.ticker}/characteristic",
            params={"isInternal": "true", "isBfpCharacteristicsToggle": "false"},
            headers=_VANGUARD_HEADERS,
            timeout=20,
        )
        characteristics.raise_for_status()
        characteristic_data = characteristics.json().get("fixedIncomeCharacteristic", {})
        fund = characteristic_data.get("fund", {})
        as_of = str(characteristic_data.get("asOfDate") or "")[:10] or None

        analytics = self.session.get(
            f"https://investor.vanguard.com/vmf/api/{VANGUARD_FUND_IDS[self.ticker]}/fundDailyAnalytics",
            headers=_VANGUARD_HEADERS,
            timeout=20,
        )
        analytics.raise_for_status()

        by_code: dict[str, Any] = {}
        for entry in analytics.json():
            code = entry.get("analyticCode")
            if code not in {"MODFDDURTN", "OAS", "AVGCNVXTY"}:
                continue
            if code not in by_code or entry.get("effectiveDate", "") > by_code[code].get(
                "effectiveDate", ""
            ):
                by_code[code] = entry

        def analytic_value(code: str) -> float | None:
            entry = by_code.get(code)
            return _parse_number(entry.get("analyticValue")) if entry else None

        return ETFAnalytics(
            ticker=self.ticker,
            provider="Vanguard",
            effective_duration=_parse_number(fund.get("averageDuration")),
            modified_duration=analytic_value("MODFDDURTN"),
            ytm=_parse_number(fund.get("yieldToMaturity")),
            oas=analytic_value("OAS"),
            convexity=analytic_value("AVGCNVXTY"),
            avg_maturity=_parse_number(fund.get("averageMaturity")),
            avg_coupon=_parse_number(fund.get("averageCoupon")),
            as_of=as_of,
        )

    def _fetch_vanguard_credit_quality(self) -> dict[str, float]:
        response = self.session.get(
            f"https://investor.vanguard.com/vmf/api/{self.ticker}/classification",
            params={"isInternal": "true", "isBfpClassificationToggle": "true"},
            headers=_VANGUARD_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        section = response.json().get("creditQuality", {})
        return {
            str(item.get("name") or ""): float(item.get("marketValuePct") or 0.0)
            for item in section.get("item", [])
            if item.get("name") is not None
        }

    def _fetch_spdr(self) -> ETFAnalytics:
        response = self.session.get(
            f"https://www.ssga.com/us/en/individual/etfs/funds/{SSGA_FUNDS[self.ticker]}",
            headers=_SSGA_HEADERS,
            timeout=20,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        raw: dict[str, float | None] = {}
        for section in soup.select("section[data-fundcomponent='true']"):
            heading = section.select_one("h2.comp-title")
            if not heading or "Fund Characteristics" not in heading.get_text():
                continue
            for row in section.select("table.tb-keyvalue tr"):
                label_cell = row.select_one("th.label")
                data_cell = row.select_one("td.data")
                if not label_cell or not data_cell:
                    continue
                label = label_cell.find(string=True, recursive=False)
                if label:
                    raw[label.strip()] = _parse_number(data_cell.get_text(strip=True))
            break

        return ETFAnalytics(
            ticker=self.ticker,
            provider="SPDR",
            effective_duration=raw.get("Option Adjusted Duration") or raw.get("Effective Duration"),
            ytm=raw.get("Yield to Maturity"),
            ytw=raw.get("Average Yield To Worst") or raw.get("Yield to Worst"),
            oas=raw.get("Option Adjusted Spread"),
            avg_maturity=raw.get("Average Maturity in Years"),
            avg_coupon=raw.get("Average Coupon"),
        )

    def _fetch_spdr_credit_quality(self) -> dict[str, float]:
        response = self.session.get(
            f"https://www.ssga.com/us/en/individual/etfs/funds/{SSGA_FUNDS[self.ticker]}",
            headers=_SSGA_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        hidden = soup.find("input", {"id": "quality-breakdown-fund"})
        if not hidden or not hidden.get("value"):
            return {}
        data = json.loads(str(hidden["value"]))
        return {
            str(item.get("name", {}).get("value") or ""): float(
                item.get("weight", {}).get("originalValue") or 0.0
            )
            for item in data.get("attrArray", [])
            if item.get("name", {}).get("value") is not None
        }

    def _fetch_invesco(self) -> ETFAnalytics:
        html = self._fetch_invesco_page_html()
        chars = self._parse_invesco_characteristics(html)
        return ETFAnalytics(
            ticker=self.ticker,
            provider="Invesco",
            effective_duration=chars.get("effective_duration"),
            modified_duration=chars.get("modified_duration"),
            ytm=chars.get("ytm"),
            ytw=chars.get("ytw"),
            avg_maturity=chars.get("avg_maturity"),
            avg_coupon=chars.get("avg_coupon"),
        )

    def _fetch_invesco_credit_quality(self) -> dict[str, float]:
        cusip, _ = INVESCO_FUNDS[self.ticker]
        weights = asyncio.run(self._fetch_invesco_breakdown_async(cusip, "creditRating"))
        return {item["name"]: float(item["value"]) for item in weights if item.get("name")}

    def _fetch_invesco_page_html(self) -> str:
        """Load the Invesco product page via Playwright to get past IP-based bot protection."""
        cusip, slug = INVESCO_FUNDS[self.ticker]
        return asyncio.run(self._fetch_invesco_html_async(cusip, slug))

    @staticmethod
    async def _fetch_invesco_html_async(cusip: str, slug: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(
                f"{_INVESCO_PRODUCT_BASE}/{slug}.html",
                wait_until="networkidle",
                timeout=60_000,
            )
            html = await page.content()
            await browser.close()
        return html

    @staticmethod
    async def _fetch_invesco_breakdown_async(cusip: str, breakdown: str) -> list[dict[str, Any]]:
        """Intercept the weightedHoldings breakdown API call made by the Invesco product page."""
        from playwright.async_api import async_playwright

        _, slug = next(
            (cusip_, slug_) for _, (cusip_, slug_) in INVESCO_FUNDS.items() if cusip_ == cusip
        )
        captured: list[dict[str, Any]] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            async def _intercept(route: Any, request: Any) -> None:
                resp = await route.fetch()
                url = request.url
                if (
                    cusip in url
                    and _INVESCO_DNG_BASE in url
                    and f"breakdown={breakdown}" in url
                    and not captured
                ):
                    try:
                        data = await resp.json()
                        captured.extend(data.get("holdingWeights", []))
                    except Exception:
                        pass
                await route.fulfill(response=resp)

            await page.route("**/*", _intercept)
            await page.goto(
                f"{_INVESCO_PRODUCT_BASE}/{slug}.html",
                wait_until="networkidle",
                timeout=60_000,
            )
            await browser.close()

        return captured

    @staticmethod
    def _parse_invesco_characteristics(html: str) -> dict[str, float | None]:
        soup = BeautifulSoup(html, "html.parser")
        raw: dict[str, str] = {}
        for row in soup.find_all(class_="tabular-list__list"):
            label_el = row.find(class_="tabular-list__label")
            value_el = row.find(class_="tabular-list__value")
            if label_el and value_el:
                label = re.sub(r"\s*\(as of [^)]+\)", "", label_el.get_text(strip=True))
                raw[label] = value_el.get_text(strip=True)
        result: dict[str, float | None] = {}
        for label, key in _INVESCO_CHAR_LABEL_MAP.items():
            text = raw.get(label, "").strip()
            if text in ("", "--", "-"):
                result[key] = None
            else:
                m = re.search(r"[-+]?[\d,]+\.?\d*", text.replace(",", ""))
                result[key] = float(m.group()) if m else None
        return result


def get_credit_quality(ticker: str, *, normalize: bool = True) -> pd.DataFrame:
    """Convenience wrapper around ETFAnalyticsClient.get_credit_quality()."""
    return ETFAnalyticsClient(ticker).get_credit_quality(normalize=normalize)
