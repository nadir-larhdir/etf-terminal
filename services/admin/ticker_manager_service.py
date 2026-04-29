"""Service for validating, adding, and removing ETF tickers across all data stores."""

from __future__ import annotations

from dataclasses import dataclass

from config import FMP_API_KEY, FMP_BASE_URL, normalize_asset_class
from services.market.fmp_client import FMPClient

# Keywords used to confirm that a new symbol is a fixed-income ETF.
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
    """Validated ticker details ready to be written to the database."""

    ticker: str
    name: str
    asset_class: str
    metadata_row: dict
    diagnostics: dict


class TickerManagerService:
    """Validate, add, and remove ETFs across the securities, metadata, and price tables."""

    def __init__(
        self,
        security_store,
        price_store,
        metadata_store,
        input_store,
        market_data_service,
        metadata_builder=None,
    ):
        self.security_store = security_store
        self.price_store = price_store
        self.metadata_store = metadata_store
        self.input_store = input_store
        self.market_data_service = market_data_service
        self.fmp_client = FMPClient(api_key=FMP_API_KEY, base_url=FMP_BASE_URL)
        self.metadata_builder = metadata_builder or self._default_metadata_builder

    def inspect_ticker(self, ticker: str, asset_class_override: str | None = None) -> TickerProfile:
        """Fetch FMP metadata for a ticker and validate it as a fixed-income ETF.

        Raises ValueError if FMP returns nothing or the ticker does not match FI keywords.
        """
        normalized = ticker.strip().upper()
        info = self.fmp_client.get_security_profile(normalized)

        if not info:
            raise ValueError(
                "Ticker not found or no metadata returned from Financial Modeling Prep."
            )

        quote_type = str(info.get("type") or info.get("quoteType") or "").upper()
        long_name = info.get("companyName") or info.get("name") or normalized
        search_blob = self._search_blob(
            [
                long_name,
                info.get("category") or "",
                info.get("description") or "",
                info.get("fundFamily") or "",
            ]
        )
        matched_keywords = [kw for kw in FIXED_INCOME_KEYWORDS if kw in search_blob]

        if quote_type != "ETF" or not matched_keywords:
            raise ValueError(
                "Ticker exists but does not look like a fixed income ETF based on Financial Modeling Prep metadata."
            )

        metadata_row = self.metadata_builder(normalized)
        asset_class = normalize_asset_class(
            asset_class_override or self._derive_asset_class(metadata_row)
        )
        metadata_row["ticker"] = normalized

        return TickerProfile(
            ticker=normalized,
            name=metadata_row.get("long_name") or long_name,
            asset_class=asset_class,
            metadata_row=metadata_row,
            diagnostics={
                "quote_type": quote_type,
                "category": info.get("category") or "",
                "matched_keywords": matched_keywords,
            },
        )

    def add_ticker(
        self, ticker: str, asset_class_override: str | None = None, period: str = "1y"
    ) -> TickerProfile:
        """Validate and persist a new ticker: securities row, metadata, and price history."""
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
            [profile.ticker], period=period, replace_existing=False
        )
        return profile

    def delete_ticker(self, ticker: str) -> None:
        """Remove a ticker from all data stores: inputs, prices, metadata, and securities."""
        normalized = ticker.strip().upper()
        self.input_store.delete_ticker(normalized)
        self.price_store.delete_ticker(normalized)
        self.metadata_store.delete_ticker(normalized)
        self.security_store.delete_ticker(normalized)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _search_blob(self, values: list[str]) -> str:
        """Concatenate and lowercase a list of strings for keyword matching."""
        return " ".join(v.lower() for v in values if v)

    def _default_metadata_builder(self, ticker: str) -> dict:
        """Build metadata using the enrichment script's production helper."""
        from scripts.market.enrich_metadata_from_fmp import build_metadata_row

        return build_metadata_row(ticker)

    def _derive_asset_class(self, metadata_row: dict) -> str:
        """Infer an asset class label from metadata text fields using keyword matching."""
        blob = self._search_blob(
            [
                metadata_row.get("category") or "",
                metadata_row.get("benchmark_index") or "",
                metadata_row.get("long_name") or "",
                metadata_row.get("description") or "",
            ]
        )
        _RULES = (
            (
                ("treasury",),
                lambda b: (
                    "UST Short"
                    if any(k in b for k in ("1-3", "short"))
                    else (
                        "UST Belly"
                        if any(k in b for k in ("3-7", "7-10", "intermediate"))
                        else "UST Long" if any(k in b for k in ("20+", "long")) else "UST Broad"
                    )
                ),
            ),
            (("high yield",), lambda _: "HY Credit"),
            (("investment grade", "corporate", "credit"), lambda _: "IG Credit"),
            (("mortgage", "mbs"), lambda _: "MBS"),
            (("municipal", "muni"), lambda _: "Municipal"),
            (("emerging markets",), lambda _: "EM Debt"),
            (("tips", "inflation"), lambda _: "Inflation-Linked"),
            (("floating rate",), lambda _: "Floating Rate"),
        )
        for keywords, label_fn in _RULES:
            if any(kw in blob for kw in keywords):
                return label_fn(blob)
        return "Fixed Income"
