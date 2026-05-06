"""Holdings tab: top ETF holdings table."""

import json
from datetime import UTC, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.styles.table_styles import DashboardTable
from fixed_income.etfs import ETF, ETFHoldings


class HoldingsTab:
    """Render the top holdings for the selected ETF."""

    def __init__(self, holdings_store) -> None:
        self.holdings_store = holdings_store
        self.table = DashboardTable()

    @staticmethod
    def _credit_quality_frame(security: ETF) -> pd.DataFrame:
        """Return parsed credit-quality weights from ETF metadata."""
        payload = security.metadata.get("credit_quality") if security.metadata else None
        if not payload:
            return pd.DataFrame(columns=["rating", "weight"])
        try:
            frame = pd.DataFrame(json.loads(payload))
        except Exception:
            return pd.DataFrame(columns=["rating", "weight"])
        if frame.empty or "rating" not in frame.columns or "weight" not in frame.columns:
            return pd.DataFrame(columns=["rating", "weight"])
        frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
        frame = frame.dropna(subset=["weight"])
        frame = frame.loc[frame["weight"] > 0].copy()
        return frame.sort_values("weight", ascending=False).reset_index(drop=True)

    @staticmethod
    def _render_credit_quality_chart(security: ETF) -> None:
        """Render a centered interactive credit rating donut chart."""
        credit = HoldingsTab._credit_quality_frame(security)
        if credit.empty:
            return

        palette = {
            "AAA": "#7FB9AA",
            "AA": "#8AA05A",
            "A": "#B7A063",
            "BBB": "#6E8740",
            "BB": "#C97C6B",
            "B": "#A55C45",
            "CCC": "#8F5C7A",
            "CC": "#73556F",
            "C": "#5C4E67",
            "D": "#7F3E3E",
            "NR": "#9E9A8C",
            "GOVT": "#7AA7C7",
            "CASH": "#C8B97E",
        }
        colors = [palette.get(rating, "#9E9A8C") for rating in credit["rating"]]
        legend_labels = [
            f"{rating:<4} {weight:>5.1f}%"
            for rating, weight in zip(credit["rating"], credit["weight"], strict=False)
        ]

        fig = go.Figure(
            go.Pie(
                labels=legend_labels,
                values=credit["weight"],
                hole=0.62,
                sort=False,
                direction="clockwise",
                marker={"colors": colors, "line": {"color": "#FBF8F1", "width": 3}},
                textinfo="none",
                customdata=credit["rating"],
                hovertemplate="%{customdata}<br>%{value:.2f}%<extra></extra>",
            )
        )
        fig.update_layout(
            title={"text": "Credit Rating Distribution", "x": 0.5, "xanchor": "center"},
            paper_bgcolor="#FBF8F1",
            plot_bgcolor="#FBF8F1",
            margin={"l": 20, "r": 20, "t": 56, "b": 20},
            height=460,
            showlegend=True,
            legend={
                "x": 1.02,
                "y": 0.5,
                "xanchor": "left",
                "yanchor": "middle",
                "font": {
                    "size": 14,
                    "color": "#1F271C",
                    "family": "SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                },
            },
        )

        left, center, right = st.columns([0.14, 0.72, 0.14])
        with center:
            st.plotly_chart(fig, use_container_width=True)

    def render(self, security: ETF) -> None:
        """Render the top-10 holdings table."""
        st.subheader("Holdings")
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

        top = top.head(10).reset_index(drop=True).copy()
        top.insert(0, "#", range(1, len(top) + 1))

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
            col
            for col in [
                "#",
                "NAME",
                "IDENTIFIER",
                "WEIGHT",
                "COUPON",
                "MATURITY",
                "PRICE",
                "MARKET VALUE",
                "FACE AMOUNT",
            ]
            if col in top.columns
        ]
        top[preferred] = top[preferred].where(pd.notna(top[preferred]), "--")

        if cached_as_of:
            st.caption(f"As of {cached_as_of}")
        st.caption("10 Top Holdings")

        self.table.render(top[preferred], hide_index=True, height=420)
        st.markdown("<div style='height:0.45rem'></div>", unsafe_allow_html=True)
        self._render_credit_quality_chart(security)
