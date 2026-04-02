import streamlit as st

from dashboard.components import InfoPanel


class NewsPage:
    """Render a market-news and macro-brief page for the fixed income ETF workflow."""

    def __init__(self) -> None:
        self.info_panel = InfoPanel()

    def render(self) -> None:
        st.markdown("### Market Brief")
        st.markdown(
            "A dedicated rates, credit, and ETF context page designed to feel like a trader's morning note. "
            "For now this is a curated shell, and later we can connect it to live headlines."
        )

        top_col1, top_col2, top_col3, top_col4 = st.columns(4)
        with top_col1:
            st.metric("REGIME", "Duration Bid")
        with top_col2:
            st.metric("CREDIT TONE", "Constructive")
        with top_col3:
            st.metric("ETF FLOW BIAS", "Defensive")
        with top_col4:
            st.metric("EVENT RISK", "Moderate")

        col1, col2 = st.columns([1.2, 1.0], vertical_alignment="top")

        with col1:
            self.info_panel.render(
                title="Morning Note",
                headline="Suggested opening brief for a fixed income ETF session",
                body=(
                    "Treasuries are the first lens: identify where the curve is leading and whether duration demand is concentrated in the front end, belly, or long end.\n\n"
                    "Credit is the second lens: watch whether IG and HY are confirming each other or whether one side is lagging the macro move.\n\n"
                    "ETF flow tone is the third lens: note whether demand is defensive, carry-seeking, or duration-led, and whether that matches price action.\n\n"
                    "Execution quality is the fourth lens: flag where participation is strong enough to support conviction rather than just a headline move."
                ),
                margin_top="0.10rem",
            )

            self.info_panel.render(
                title="Key Headlines",
                headline="Prototype layout for the live news feed",
                body=(
                    "Rates: Treasury yields retrace after a strong duration bid, with the belly leading the move.\n\n"
                    "Credit: IG spreads remain orderly while HY beta lags, suggesting selective rather than broad risk appetite.\n\n"
                    "ETF flows: core duration products stay firm as investors rotate toward higher-quality carry.\n\n"
                    "Macro: traders prepare for the next catalyst with focus on inflation, auctions, and central-bank tone."
                ),
                accent_color="#00ADB5",
            )

        with col2:
            self.info_panel.render_note(
                title="Rates Focus",
                body="Watch whether the long end is confirming the move or whether the belly remains the cleanest expression of duration demand.",
            )
            self.info_panel.render_note(
                title="Credit Focus",
                body="Look for confirmation between LQD, VCIT, HYG, and JNK before calling the move a broad credit regime shift.",
            )
            self.info_panel.render_note(
                title="ETF Flow Focus",
                body="Track whether allocations are moving into core bond beta, short duration defense, or spread carry.",
            )
            self.info_panel.render_note(
                title="Event Watch",
                body="Use this block for CPI, payrolls, Treasury auctions, refunding, and FOMC timing with one-line trading relevance.",
            )

        st.markdown("### Coverage Map")
        coverage_col1, coverage_col2, coverage_col3 = st.columns(3)
        with coverage_col1:
            self.info_panel.render(
                title="Rates",
                headline="Curve, auctions, and policy tone",
                body="This section can hold front-end, belly, and long-end headlines plus Treasury supply context and central-bank commentary.",
                margin_top="0.10rem",
                margin_bottom="0.20rem",
            )
        with coverage_col2:
            self.info_panel.render(
                title="Credit",
                headline="Spread tone and risk appetite",
                body="This section can cover IG vs HY leadership, spread decompression, issuance tone, and sector-level stress signals.",
                margin_top="0.10rem",
                margin_bottom="0.20rem",
                accent_color="#00ADB5",
            )
        with coverage_col3:
            self.info_panel.render(
                title="ETF Market",
                headline="Flows, liquidity, and implementation",
                body="This section can focus on where ETF turnover, creation-redemption activity, and allocator demand are changing execution conditions.",
                margin_top="0.10rem",
                margin_bottom="0.20rem",
                accent_color="#FFD166",
            )
