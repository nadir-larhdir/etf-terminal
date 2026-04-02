import pandas as pd
import streamlit as st

from config import normalize_asset_class
from dashboard.components import DashboardTable, InfoPanel


class HomePage:
    """Render the homepage that introduces the project and frames the market context."""

    def __init__(self, price_repo):
        self.price_repo = price_repo
        self.info_panel = InfoPanel()
        self.table = DashboardTable()

    def render(self, securities: pd.DataFrame) -> None:
        latest_date = self._latest_market_date(securities)
        latest_date_label = latest_date if latest_date else "Awaiting history sync"
        bucket_summary = self._build_bucket_summary(securities)
        asset_class_count = len(bucket_summary.index)

        left_col, right_col = st.columns([1.55, 1.0], vertical_alignment="top")

        with left_col:
            st.markdown("### ETF Terminal")
            st.markdown(
                "A fixed income ETF analytics workspace built to track liquidity, relative value, "
                "market structure, and cross-market regime shifts."
            )

            stats_col1, stats_col2, stats_col3 = st.columns(3)
            with stats_col1:
                st.metric("ACTIVE ETFS", f"{len(securities):,}")
            with stats_col2:
                st.metric("UNIVERSE BUCKETS", f"{asset_class_count:,}")
            with stats_col3:
                st.metric("LATEST MARKET DATE", latest_date_label)

            self.info_panel.render(
                title="Project Overview",
                headline="A focused terminal for fixed income ETF decision support",
                body=(
                    "ETF Terminal is designed to organize price action, liquidity, and relative-value signals "
                    "for bond ETF markets in one place. The workflow starts with a market framing layer, then "
                    "moves into security-level analysis, charting, and RV pair work."
                ),
                footer=(
                    "Core lenses: <span style='color:#F3F0E8; font-weight:700;'>rates, credit, liquidity, "
                    "execution conditions, and mean-reversion context.</span>"
                ),
            )

            self.info_panel.render(
                title="Morning Setup",
                headline="What the homepage should help you answer quickly",
                body=(
                    "Where is duration leading? Is credit trading defensively or constructively? Which ETFs "
                    "are showing unusual participation? Where are the cleanest relative-value dislocations? "
                    "The home layer is meant to turn the dashboard into a market prep workflow rather than only a chart screen."
                ),
                accent_color="#00ADB5",
            )

        with right_col:
            self.info_panel.render(
                title="Macro Pulse",
                headline="Daily framing ideas",
                body=(
                    "Rates: watch the belly and long-end for duration leadership.\n\n"
                    "Credit: monitor whether IG beta and HY beta are confirming each other.\n\n"
                    "Liquidity: compare current ETF volume to 30-day norms for execution quality.\n\n"
                    "Flows: focus on whether allocator demand is moving toward defense, carry, or duration."
                ),
                margin_top="0.10rem",
            )

            self.info_panel.render(
                title="News Layer",
                headline="Proposed homepage news section",
                body=(
                    "This area can hold a concise market brief with 5 to 8 headlines across rates, credit, "
                    "ETF flow, and macro events. We can start with a manual note, then move to a live feed."
                ),
                accent_color="#FFD166",
            )

        st.markdown("### Universe Snapshot")
        self.table.render(bucket_summary, hide_index=True, height=280)

        st.markdown("### Why This Layout")
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        with insight_col1:
            self.info_panel.render_note(
                title="Front Door",
                body="The homepage introduces the product and gives context before users drop into a single ETF.",
            )
        with insight_col2:
            self.info_panel.render_note(
                title="Macro Framing",
                body="A daily market brief can make the app feel like a live fixed income workspace, not just a stored database.",
            )
        with insight_col3:
            self.info_panel.render_note(
                title="Next Extensions",
                body="We can add focus ETF, pair idea of the day, and key macro event tiles once the homepage shell feels right.",
            )

    def _latest_market_date(self, securities: pd.DataFrame) -> str | None:
        tickers = securities["ticker"].astype(str).tolist() if not securities.empty else []
        latest_dates = self.price_repo.get_latest_stored_dates(tickers)
        if not latest_dates:
            return None
        return max(latest_dates.values())

    def _build_bucket_summary(self, securities: pd.DataFrame) -> pd.DataFrame:
        if securities.empty:
            return pd.DataFrame(columns=["ASSET CLASS", "ETF COUNT", "EXAMPLE TICKERS"])

        working_frame = securities.copy()
        working_frame["asset_class"] = (
            working_frame["asset_class"]
            .fillna("Other")
            .astype(str)
            .str.strip()
            .map(normalize_asset_class)
        )

        grouped = (
            working_frame.groupby("asset_class", dropna=False)["ticker"]
            .agg(["count", lambda values: ", ".join(list(values)[:4])])
            .reset_index()
            .rename(
                columns={
                    "asset_class": "ASSET CLASS",
                    "count": "ETF COUNT",
                    "<lambda_0>": "EXAMPLE TICKERS",
                }
            )
            .sort_values(["ETF COUNT", "ASSET CLASS"], ascending=[False, True])
            .reset_index(drop=True)
        )
        grouped["ETF COUNT"] = grouped["ETF COUNT"].astype(int)
        return grouped
