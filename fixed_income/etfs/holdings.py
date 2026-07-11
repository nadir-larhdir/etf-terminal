from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO, StringIO

import pandas as pd
import requests

ISHARES_HOLDINGS_FUNDS = {
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
    "STIP": ("239450", "ishares-05-year-tips-bond-etf"),
    "TIP": ("239467", "ishares-tips-bond-etf"),
    "TLT": ("239454", "ishares-20-year-treasury-bond-etf"),
}

VANGUARD_HOLDINGS_FUNDS = {
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

SSGA_HOLDINGS_FUNDS = {
    "JNK": "jnk",
    "SJNK": "sjnk",
    "SPHY": "sphy",
    "SPAB": "spab",
    "SPIB": "spib",
    "SPSB": "spsb",
    "SPTI": "spti",
    "SPTL": "sptl",
    "FLRN": "flrn",
}

# ticker → (cusip, page-slug)
INVESCO_HOLDINGS_FUNDS = {
    "PCY": ("46138E784", "invesco-emerging-markets-sovereign-debt-etf"),
}

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
_UA_FULL = f"{_UA} (KHTML, like Gecko) Version/26.3.1 Safari/605.1.15"
_SSGA_HOLDINGS_BASE = (
    "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us"
)
_ISHARES_HOLDINGS_DOCUMENT_URL = (
    "https://www.blackrock.com/varnish-api/blk-one01-product-data"
    "/product-data/api/v1/get-fund-document"
)

_VANGUARD_HEADERS = {"User-Agent": _UA}
_ISHARES_HEADERS = {"User-Agent": _UA, "Referer": "https://www.ishares.com/us/"}


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _normalize_cusip(value) -> str | None:
    text = None if value is None or pd.isna(value) else str(value).strip()
    if not text or text == "-":
        return None
    return text[2:-1] if len(text) == 12 else text


def _mbs_date(value) -> str | None:
    if not value:
        return None
    parts = str(value).split("-")
    return parts[-1].strip() if len(parts) > 1 else parts[0].strip()


def _ishares_csv_header_row(text: str) -> int:
    """Return the row index of the holdings CSV header in an iShares response."""
    for idx, line in enumerate(text.splitlines()):
        columns = [part.strip().strip('"') for part in line.split(",")]
        if {"Name", "Sector", "Weight (%)"}.issubset(columns):
            return idx
    preview = text.lstrip()[:80].replace("\n", " ")
    if preview.lower().startswith(("<!doctype html", "<html")):
        raise RuntimeError("iShares returned an HTML page instead of holdings CSV.")
    raise RuntimeError("iShares holdings CSV header row not found.")


def _ishares_fund_document_params(product_id: str) -> dict[str, str]:
    return {
        "appType": "PRODUCT_PAGE",
        "appSubType": "ISHARES",
        "targetSite": "us-ishares",
        "locale": "en_US",
        "portfolioId": product_id,
        "component": "holdings",
        "userType": "individual",
        "asOfDate": "",
    }


class ETFHoldings:
    _COLS = [
        "name",
        "cusip",
        "isin",
        "sedol",
        "weight",
        "coupon",
        "maturity_dt",
        "price",
        "market_value",
        "face_amount",
        "ticker",
    ]

    def __init__(self, ticker: str, session: requests.Session | None = None) -> None:
        self.ticker = ticker.strip().upper()
        self.session = session or requests.Session()
        if self.ticker in ISHARES_HOLDINGS_FUNDS:
            self.provider = "ishares"
        elif self.ticker in VANGUARD_HOLDINGS_FUNDS:
            self.provider = "vanguard"
        elif self.ticker in SSGA_HOLDINGS_FUNDS:
            self.provider = "spdr"
        elif self.ticker in INVESCO_HOLDINGS_FUNDS:
            self.provider = "invesco"
        else:
            raise ValueError(f"Unknown ticker '{ticker}'")

    def get(self) -> pd.DataFrame:
        return getattr(self, f"_load_{self.provider}")()

    def _load_ishares(self) -> pd.DataFrame:
        product_id, slug = ISHARES_HOLDINGS_FUNDS[self.ticker]
        csv_text, header_row = self._fetch_ishares_holdings_csv(product_id, slug)
        frame = (
            pd.read_csv(
                StringIO(csv_text),
                skiprows=header_row,
                thousands=",",
                na_values=["-", "--", ""],
            )
            .dropna(subset=["Sector"])
            .rename(
                columns={
                    "Name": "name",
                    "CUSIP": "cusip",
                    "ISIN": "isin",
                    "Weight (%)": "weight",
                    "Coupon (%)": "coupon",
                    "Market Value": "market_value",
                    "Par Value": "face_amount",
                    "Maturity": "maturity_dt",
                    "Asset Class": "asset_class",
                }
            )
        )
        for column in ["market_value", "face_amount"]:
            if column in frame.columns:
                frame[column] = _to_num(
                    frame[column].astype(str).str.replace(r"[$,]", "", regex=True)
                )
        frame["maturity_dt"] = _to_date(frame.get("maturity_dt"))
        frame["price"] = frame["market_value"] / frame["face_amount"] * 100
        if "asset_class" in frame.columns:
            frame = frame[
                frame["asset_class"]
                .astype(str)
                .str.lower()
                .isin(["bond", "fixed income", "corporate bond", "treasury", "agency", "municipal"])
            ]
        return self._finalize(frame)

    def _fetch_ishares_holdings_csv(self, product_id: str, slug: str) -> tuple[str, int]:
        urls = [
            (_ISHARES_HOLDINGS_DOCUMENT_URL, _ishares_fund_document_params(product_id)),
            (
                f"https://www.ishares.com/us/products/{product_id}/{slug}" "/1467271812596.ajax",
                {"tab": "portfolio", "fileType": "csv"},
            ),
        ]
        errors: list[str] = []
        for url, params in urls:
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=_ISHARES_HEADERS,
                    timeout=30,
                )
                response.raise_for_status()
                return response.text, _ishares_csv_header_row(response.text)
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        raise RuntimeError("iShares holdings CSV unavailable. " + " | ".join(errors))

    def _load_vanguard(self) -> pd.DataFrame:
        url = f"https://investor.vanguard.com/vmf/api" f"/{self.ticker}/portfolio-holding/bond.json"

        first = self.session.get(
            url,
            params={"start": 1, "count": 500},
            headers=_VANGUARD_HEADERS,
            timeout=20,
        )
        first.raise_for_status()
        payload = first.json()
        total = int(payload.get("size", 0))
        entities = list(payload.get("fund", {}).get("entity", []))  # ← safe get

        def fetch_page(start: int) -> list[dict]:
            r = self.session.get(
                url,
                params={"start": start, "count": 500},
                headers=_VANGUARD_HEADERS,
                timeout=20,
            )
            r.raise_for_status()
            return r.json().get("fund", {}).get("entity", [])  # ← safe get

        if total > 500:
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(fetch_page, s) for s in range(501, total + 1, 500)]
                for future in as_completed(futures):
                    entities.extend(future.result())

        rows = [
            {
                "name": e.get("longName") or e.get("shortName"),
                "cusip": e.get("cusip") or None,
                "isin": e.get("isin") or None,
                "sedol": e.get("sedol") or None,
                "weight": e.get("percentWeight"),
                "coupon": e.get("couponRate"),
                "maturity_dt": _mbs_date(e.get("maturityDate")),
                "market_value": e.get("marketValue"),
                "face_amount": e.get("faceAmount"),
            }
            for e in entities
        ]

        frame = pd.DataFrame(rows)
        frame["weight"] = _to_num(frame["weight"])
        frame["coupon"] = _to_num(frame["coupon"])
        frame["face_amount"] = _to_num(frame["face_amount"])
        frame["maturity_dt"] = _to_date(frame["maturity_dt"])
        frame["price"] = frame["market_value"] / frame["face_amount"] * 100
        return self._finalize(frame)

    def _load_spdr(self) -> pd.DataFrame:
        slug = SSGA_HOLDINGS_FUNDS[self.ticker]
        url = f"{_SSGA_HOLDINGS_BASE}/holdings-daily-us-en-{slug}.xlsx"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        frame = pd.read_excel(BytesIO(response.content), sheet_name="holdings", header=4).rename(
            columns={
                "Name": "name",
                "Identifier": "isin",
                "SEDOL": "sedol",
                "Weight": "weight",
                "Coupon": "coupon",
                "Par Value": "face_amount",
                "Market Value": "market_value",
                "Maturity": "maturity_dt",
            }
        )
        for column in ["weight", "coupon", "face_amount", "market_value"]:
            if column in frame.columns:
                frame[column] = _to_num(frame[column])
        if "cusip" in frame.columns:
            frame["cusip"] = frame["cusip"].apply(_normalize_cusip)
        frame["maturity_dt"] = _to_date(frame.get("maturity_dt"))
        frame["price"] = frame["market_value"] / frame["face_amount"] * 100
        return self._finalize(frame)

    def _load_invesco(self) -> pd.DataFrame:
        cusip, slug = INVESCO_HOLDINGS_FUNDS[self.ticker]
        holdings_raw = asyncio.run(self._fetch_invesco_holdings_async(cusip, slug))
        rows = []
        for h in holdings_raw:
            mv = h.get("marketValueBase")
            fa = h.get("units")
            rows.append(
                {
                    "name": h.get("issuerName"),
                    "cusip": h.get("cusip"),
                    "weight": h.get("percentageOfTotalNetAssets"),
                    "coupon": h.get("coupon"),
                    "maturity_dt": h.get("maturityDate"),
                    "market_value": mv,
                    "face_amount": fa,
                    "price": (mv / fa * 100) if mv and fa else None,
                }
            )
        frame = pd.DataFrame(rows)
        frame["maturity_dt"] = _to_date(frame["maturity_dt"])
        return self._finalize(frame)

    @staticmethod
    async def _fetch_invesco_holdings_async(cusip: str, slug: str) -> list[dict]:
        """Intercept the holdings/fund XHR made by the Invesco product page.

        dng-api.invesco.com returns 406 to bare programmatic requests; loading the
        product page first via Playwright plants the session cookies the CDN requires.
        """
        from playwright.async_api import async_playwright

        _base = "https://www.invesco.com/us/en/financial-products/etfs"
        _dng = "https://dng-api.invesco.com"
        captured: list[dict] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            async def _intercept(route, request):
                resp = await route.fetch()
                url = request.url
                if cusip in url and _dng in url and "holdings/fund" in url and not captured:
                    try:
                        data = await resp.json()
                        captured.extend(data.get("holdings", []))
                    except Exception:
                        pass
                await route.fulfill(response=resp)

            await page.route("**/*", _intercept)
            await page.goto(
                f"{_base}/{slug}.html",
                wait_until="networkidle",
                timeout=60_000,
            )
            await browser.close()

        return captured

    def _finalize(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame["ticker"] = self.ticker
        return (
            frame[[column for column in self._COLS if column in frame.columns]]
            .dropna(subset=["name"])
            .reset_index(drop=True)
        )
