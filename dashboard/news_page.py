from datetime import datetime

import streamlit as st

from dashboard.components import InfoPanel
from services.news import NewsFeedService


@st.cache_data(ttl=3600, show_spinner=False)
def load_news_feeds() -> tuple[dict[str, dict], str | None]:
    """Load live RSS feeds for the news page with an hourly cache window."""
    service = NewsFeedService()
    try:
        feed_data = service.fetch_all(limit_per_feed=6)
        return feed_data, None
    except Exception as exc:
        return {}, str(exc)


class NewsPage:
    """Render a market-news and macro-brief page for the fixed income ETF workflow."""

    def __init__(self) -> None:
        self.info_panel = InfoPanel()

    def _dedupe_feeds(self, feed_data: dict[str, dict]) -> dict[str, list[dict]]:
        seen_keys: set[str] = set()
        deduped: dict[str, list[dict]] = {}

        for feed_key in ["rates", "credit", "macro"]:
            items = feed_data.get(feed_key, {}).get("items", [])
            unique_items: list[dict] = []
            for item in items:
                key = (
                    str(item.get("title", "")).strip().lower(),
                    str(item.get("source", "")).strip().lower(),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                unique_items.append(item)
            deduped[feed_key] = unique_items

        return deduped

    def _format_timestamp(self, value: str | None) -> str:
        if not value:
            return "time unavailable"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return "time unavailable"

    def _pick_top_story(self, grouped_items: dict[str, list[dict]]) -> tuple[str, dict] | tuple[None, None]:
        for feed_key in ["rates", "credit", "macro"]:
            items = grouped_items.get(feed_key, [])
            if items:
                return feed_key, items[0]
        return None, None

    def _render_featured_headline(self, title: str, items: list[dict], *, accent_color: str) -> None:
        if not items:
            self.info_panel.render_note(
                title=title,
                body="No headlines were returned for this feed right now.",
                accent_color=accent_color,
            )
            return

        featured = items[0]
        body = (
            f"<a href='{featured['link']}' target='_blank' "
            f"style='color:#B8B1A3;text-decoration:none;font-weight:700;font-size:0.95rem;'>"
            f"{featured['title']}</a><br><br>"
            f"<span style='color:#B8B1A3;font-size:0.78rem;'>"
            f"{featured['source']} | {self._format_timestamp(featured.get('published_at'))}</span>"
        )

        self.info_panel.render(
            title=title,
            headline="Featured headline",
            body=body,
            accent_color=accent_color,
            margin_top="0.10rem",
            margin_bottom="0.20rem",
        )

    def _render_headline_list(self, items: list[dict], *, max_items: int = 5) -> None:
        if len(items) <= 1:
            return

        rows = []
        for item in items[1:max_items + 1]:
            rows.append(
                f"<div style='padding:0.38rem 0;border-bottom:1px solid #1A1A1A;'>"
                f"<a href='{item['link']}' target='_blank' style='color:#B8B1A3;text-decoration:none;'>"
                f"{item['title']}</a><br>"
                f"<span style='color:#8D877B;font-size:0.75rem;'>{item['source']} | {self._format_timestamp(item.get('published_at'))}</span>"
                f"</div>"
            )

        st.markdown(
            (
                "<div style='border:1px solid #20252E;background:#050505;padding:0.15rem 0.60rem 0.35rem 0.60rem;"
                "border-radius:2px;margin-top:0.15rem;margin-bottom:0.55rem;'>"
                "<div style='color:#B8B1A3;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.45px;"
                "margin:0.30rem 0 0.20rem 0;font-weight:700;'>More Headlines</div>"
                f"{''.join(rows)}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    def render(self) -> None:
        feed_data, feed_error = load_news_feeds()
        deduped_feed_data = self._dedupe_feeds(feed_data)
        rates_items = deduped_feed_data.get("rates", [])
        credit_items = deduped_feed_data.get("credit", [])
        macro_items = deduped_feed_data.get("macro", [])
        top_story_bucket, top_story = self._pick_top_story(deduped_feed_data)

        st.markdown(
            "<div style='color:#8D877B;font-size:1.15rem;font-weight:700;text-transform:uppercase;"
            "letter-spacing:0.6px;margin-bottom:0.35rem;'>Market Brief</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "A dedicated rates, credit, ETF, and macro context page designed to feel like a trader's morning note."
        )
        st.caption("Headlines refresh automatically every hour.")

        if feed_error:
            st.caption(f"Live feed fetch failed: {feed_error}")
        elif top_story is not None:
            accent_map = {
                "rates": "#5DA9E9",
                "credit": "#FF9F1A",
                "macro": "#FF5A36",
            }
            section_label = {
                "rates": "Top Story | Rates",
                "credit": "Top Story | Credit And ETFs",
                "macro": "Top Story | Macro",
            }.get(top_story_bucket or "", "Top Story")
            self.info_panel.render(
                title=section_label,
                headline="Lead headline",
                body=(
                    f"<a href='{top_story['link']}' target='_blank' "
                    f"style='color:#B8B1A3;text-decoration:none;font-weight:700;font-size:1.08rem;line-height:1.45;'>"
                    f"{top_story['title']}</a><br><br>"
                    f"<span style='color:#B8B1A3;font-size:0.80rem;'>"
                    f"{top_story['source']} | {self._format_timestamp(top_story.get('published_at'))}</span>"
                ),
                accent_color=accent_map.get(top_story_bucket or "", "#FF9F1A"),
                margin_top="0.10rem",
                margin_bottom="0.35rem",
            )

        col1, col2, col3 = st.columns(3, vertical_alignment="top")
        with col1:
            self._render_featured_headline("Rates", rates_items, accent_color="#5DA9E9")
            self._render_headline_list(rates_items)
        with col2:
            self._render_featured_headline("Credit And ETFs", credit_items, accent_color="#FF9F1A")
            self._render_headline_list(credit_items)
        with col3:
            self._render_featured_headline("Macro", macro_items, accent_color="#FF5A36")
            self._render_headline_list(macro_items)

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
