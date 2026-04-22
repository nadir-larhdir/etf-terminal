from __future__ import annotations

from dataclasses import dataclass

from config import FMP_API_KEY, FMP_BASE_URL, normalize_asset_class
from services.market.fmp_client import FMPClient


# Keywords used to decide whether a new symbol looks like a fixed-income ETF.
FIXED_INCOME_KEYWORDS = (
    "bond",
    "treasury",
    "fixed income",
    "corporate",
    "credit",
    "muni",
    "municipal",
    "mortgage",
    "mbs",
    "floating rate",
    "ultra short",
    "short-term",
    "emerging markets bond",
    "high yield",
    "investment grade",
    "tips",
    "inflation protected",
)


@dataclass
class TickerProfile:
    """Carry validated ticker details before they are persisted to the database."""

    ticker: str
    name: str
    asset_class: str
    metadata_row: dict
    diagnostics: dict


class TickerManagerService:
    """Validate, add, and remove ETFs across the securities, metadata, and price tables."""

    def __init__(self, security_store, price_store, metadata_store, input_store, market_data_service):
        self.security_store = security_store
        self.price_store = price_store
        self.metadata_store = metadata_store
        self.input_store = input_store
        self.market_data_service = market_data_service
        self.fmp_client = FMPClient(api_key=FMP_API_KEY, base_url=FMP_BASE_URL)

    def _search_blob(self, values: list[str]) -> str:
        return " ".join(value.lower() for value in values if value)

    def inspect_ticker(self, ticker: str, asset_class_override: str | None = None) -> TickerProfile:
        from scripts.market.enrich_metadata_from_fmp import build_metadata_row

        normalized = ticker.strip().upper()
        info = self.fmp_client.get_security_profile(normalized)

        quote_type = str(info.get("type") or info.get("quoteType") or "").upper()
        long_name = info.get("companyName") or info.get("name") or normalized
        category = info.get("category") or ""
        summary = info.get("description") or ""
        fund_family = info.get("fundFamily") or ""

        search_blob = self._search_blob([long_name, category, summary, fund_family])
        matched_keywords = [
            keyword for keyword in FIXED_INCOME_KEYWORDS if keyword in search_blob
        ]
        is_fixed_income = quote_type == "ETF" and bool(matched_keywords)

        if not info:
            raise ValueError("Ticker not found or no metadata returned from Financial Modeling Prep.")

        if not is_fixed_income:
            raise ValueError(
                "Ticker exists but does not look like a fixed income ETF based on Financial Modeling Prep metadata."
            )

        metadata_row = build_metadata_row(normalized)
        inferred_asset_class = asset_class_override or self._derive_asset_class(metadata_row)
        asset_class = normalize_asset_class(inferred_asset_class)
        metadata_row["ticker"] = normalized

        return TickerProfile(
            ticker=normalized,
            name=metadata_row.get("long_name") or long_name,
            asset_class=asset_class,
            metadata_row=metadata_row,
            diagnostics={
                "quote_type": quote_type,
                "category": category,
                "matched_keywords": matched_keywords,
            },
        )

    def add_ticker(
        self,
        ticker: str,
        asset_class_override: str | None = None,
        period: str = "1y",
    ) -> TickerProfile:
        profile = self.inspect_ticker(ticker, asset_class_override=asset_class_override)

        self.security_store.upsert_securities(
            [
                {
                    "ticker": profile.ticker,
                    "name": profile.name,
                    "asset_class": profile.asset_class,
                    "active": 1,
                }
            ],
            update_existing=True,
        )
        self.metadata_store.upsert_metadata([profile.metadata_row])
        self.market_data_service.sync_price_history(
            [profile.ticker],
            period=period,
            replace_existing=False,
        )
        return profile

    def delete_ticker(self, ticker: str):
        normalized = ticker.strip().upper()
        self.input_store.delete_ticker(normalized)
        self.price_store.delete_ticker(normalized)
        self.metadata_store.delete_ticker(normalized)
        self.security_store.delete_ticker(normalized)

    def _derive_asset_class(self, metadata_row: dict) -> str:
        category = str(metadata_row.get("category") or "")
        benchmark = str(metadata_row.get("benchmark_index") or "")
        long_name = str(metadata_row.get("long_name") or "")
        description = str(metadata_row.get("description") or "")

        search_blob = self._search_blob([category, benchmark, long_name, description])

        if "treasury" in search_blob:
            if "1-3" in search_blob or "short" in search_blob:
                return "UST Short"
            if "3-7" in search_blob or "7-10" in search_blob or "intermediate" in search_blob:
                return "UST Belly"
            if "20+" in search_blob or "long" in search_blob:
                return "UST Long"
            return "UST Broad"
        if "high yield" in search_blob:
            return "HY Credit"
        if "investment grade" in search_blob or "corporate" in search_blob or "credit" in search_blob:
            return "IG Credit"
        if "mortgage" in search_blob or "mbs" in search_blob:
            return "MBS"
        if "municipal" in search_blob or "muni" in search_blob:
            return "Municipal"
        if "emerging markets" in search_blob:
            return "EM Debt"
        if "tips" in search_blob or "inflation" in search_blob:
            return "Inflation-Linked"
        if "floating rate" in search_blob:
            return "Floating Rate"
        return "Fixed Income"
