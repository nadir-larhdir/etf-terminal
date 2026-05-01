from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

ISHARES_FUNDS = {
    "AGG": ("239458", "ishares-core-us-aggregate-bond-etf"),
    "EMB": ("239572", "ishares-jp-morgan-usd-emerging-markets-bond-etf"),
    "FLOT": ("239534", "ishares-floating-rate-bond-etf"),
    "GOVT": ("239458", "ishares-us-treasury-bond-etf"),
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

INVESCO_FUNDS = {
    "PCY": "46138E784",
}

PROVIDER_BY_TICKER = {
    **dict.fromkeys(ISHARES_FUNDS, "iShares"),
    **dict.fromkeys(VANGUARD_FUND_IDS, "Vanguard"),
    **dict.fromkeys(SSGA_FUNDS, "SPDR"),
    **dict.fromkeys(INVESCO_FUNDS, "Invesco"),
}

_ISHARES_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Referer": "https://www.ishares.com/us/",
}
_SSGA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
}
_VANGUARD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
}
_INVESCO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3.1 Safari/605.1.15",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.invesco.com",
    "Referer": "https://www.invesco.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


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


def _parse_number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = re.search(r"[-+]?\d[\d,]*\.?\d*", str(value).replace(",", ""))
    return float(match.group().replace(",", "")) if match else None


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

    def _fetch_ishares(self) -> ETFAnalytics:
        product_id, slug = ISHARES_FUNDS[self.ticker]
        response = self.session.get(
            f"https://www.ishares.com/us/products/{product_id}/{slug}",
            headers=_ISHARES_HEADERS,
            timeout=20,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        section = soup.find("div", attrs={"data-componentname": "Fundamentals And Risk"})
        if not section:
            raise RuntimeError(f"[{self.ticker}] iShares fundamentals section not found")

        raw: dict[str, float | None] = {}
        for item in section.select("div.product-data-item"):
            caption = item.select_one("div.caption")
            data = item.select_one("div.data")
            if not caption or not data:
                continue
            label = caption.find(string=True, recursive=False)
            if label:
                raw[label.strip()] = _parse_number(data.get_text(strip=True))

        return ETFAnalytics(
            ticker=self.ticker,
            provider="iShares",
            effective_duration=raw.get("Effective Duration"),
            modified_duration=raw.get("Modified Duration"),
            ytm=raw.get("Average Yield to Maturity"),
            ytw=raw.get("Yield to Worst") or raw.get("Average Yield To Worst"),
            oas=raw.get("Option Adjusted Spread"),
            convexity=raw.get("Convexity"),
            avg_maturity=raw.get("Weighted Avg Maturity"),
            avg_coupon=raw.get("Weighted Avg Coupon"),
        )

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

        by_code = {}
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

    def _fetch_invesco(self) -> ETFAnalytics:
        response = self.session.get(
            f"https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/{INVESCO_FUNDS[self.ticker]}",
            params={
                "expand": "nav",
                "idType": "cusip",
                "variationType": "fundCharacteristics",
                "productType": "ETF",
            },
            headers=_INVESCO_HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        return ETFAnalytics(
            ticker=self.ticker,
            provider="Invesco",
            effective_duration=_parse_number(data.get("unauditedEffectiveDuration")),
            modified_duration=_parse_number(data.get("unauditedModifiedDuration")),
            ytm=_parse_number(data.get("unauditedYieldToMaturity")),
            ytw=_parse_number(data.get("unauditedYieldToWorst")),
            avg_maturity=_parse_number(data.get("unauditedYearsToMaturity")),
            avg_coupon=_parse_number(data.get("unauditedWeightedAverageCoupon")),
            as_of=data.get("effectiveDate"),
        )
