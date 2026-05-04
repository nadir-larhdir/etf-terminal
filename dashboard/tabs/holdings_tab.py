"""Holdings tab: top ETF holdings table."""

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from dashboard.styles.table_styles import DashboardTable
from fixed_income.etfs import ETF, ETFHoldings


class HoldingsTab:
    """Render the top holdings for the selected ETF."""

    def __init__(self, holdings_store) -> None:
        self.holdings_store = holdings_store
        self.table = DashboardTable()

    def render(self, security: ETF) -> None:
        st.subheader("Top 10 Holdings")
        holdings = self.holdings_store.get_latest_holdings(security.ticker, limit=10)
        cached_as_of = self.holdings_store.get_latest_as_of_date(security.ticker)

        if holdings.empty:
            try:
                holdings = ETFHoldings(security.ticker).get()
                self.holdings_store.replace_holdings(
                    security.ticker,
                    holdings,
                    as_of_date=datetime.now(UTC).date().isoformat(),
                )
                holdings = self.holdings_store.get_latest_holdings(security.ticker, limit=10)
                cached_as_of = self.holdings_store.get_latest_as_of_date(security.ticker)
            except Exception as exc:
                st.warning(f"Unable to load holdings for {security.ticker}: {exc}")
                return

        if holdings.empty:
            st.info(f"No holdings available for {security.ticker}.")
            return

        top = holdings.copy()
        if "weight" in top.columns:
            top["weight"] = pd.to_numeric(top["weight"], errors="coerce")
            top = top.sort_values("weight", ascending=False)

        top = top.head(10).copy()
        if "maturity_dt" in top.columns:
            top["maturity_dt"] = pd.to_datetime(top["maturity_dt"], errors="coerce").dt.strftime(
                "%Y-%m-%d"
            )
        top["identifier"] = top.get("isin")
        if "cusip" in top.columns:
            top["identifier"] = top["identifier"].where(pd.notna(top["identifier"]), top["cusip"])

        top = top.rename(
            columns={
                "name": "NAME",
                "identifier": "IDENTIFIER",
                "sedol": "SEDOL",
                "weight": "WEIGHT",
                "coupon": "COUPON",
                "maturity_dt": "MATURITY",
                "price": "PRICE",
                "market_value": "MARKET VALUE",
                "face_amount": "FACE AMOUNT",
            }
        )
        preferred = [
            column
            for column in [
                "NAME",
                "IDENTIFIER",
                "WEIGHT",
                "COUPON",
                "MATURITY",
                "PRICE",
                "MARKET VALUE",
                "FACE AMOUNT",
            ]
            if column in top.columns
        ]
        top[preferred] = top[preferred].where(pd.notna(top[preferred]), "--")
        if cached_as_of:
            st.caption(f"As of {cached_as_of}")
        self.table.render(top[preferred], hide_index=True, height=420)
