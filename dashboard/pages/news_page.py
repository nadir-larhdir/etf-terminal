from datetime import datetime

import pandas as pd
import streamlit as st

from dashboard.cache import app_cache_key, cached_latest_feature_values
from dashboard.components import InfoPanel
from dashboard.perf import timed_block
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

    SNAPSHOT_FEATURES = {
        "UST_10Y_LEVEL": ("10Y", "{:.2f}%"),
        "UST_2S10S": ("2s10s", "{:.0f}bp"),
        "BEI_5Y": ("5Y BEI", "{:.2f}%"),
        "FEDFUNDS_LEVEL": ("Fed Funds", "{:.2f}%"),
        "UNRATE_LEVEL": ("Unrate", "{:.2f}%"),
    }

    EVENT_WATCH = [
        ("CPI", "Inflation tone"),
        ("Payrolls", "Labor pulse"),
        ("FOMC", "Policy path"),
        ("Auctions", "Treasury supply"),
    ]

    def __init__(self, macro_feature_store) -> None:
        self.info_panel = InfoPanel()
        self.macro_feature_store = macro_feature_store

    def _render_news_link_styles(self) -> None:
        st.markdown(
            """
            <style>
            .bb-news-link {
                color: #F3F0E8 !important;
                text-decoration: none !important;
                transition: color 0.18s ease;
            }
            .bb-news-link--rates:hover {
                color: #5DA9E9 !important;
            }
            .bb-news-link--credit:hover {
                color: #FF9F1A !important;
            }
            .bb-news-link--macro:hover {
                color: #FF5A36 !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _news_link_style(self, *, font_size: str, weight: int = 700, line_height: str = "1.4") -> str:
        return (
            f"color:#F3F0E8;text-decoration:none;font-weight:{weight};font-size:{font_size};line-height:{line_height};"
            "transition:color 0.18s ease;"
        )

    def _news_link_class(self, bucket: str) -> str:
        return f"bb-news-link bb-news-link--{bucket}"

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

    def _headline_tag(self, title: str, bucket: str) -> str:
        title_lower = title.lower()
        keyword_map = {
            "rates": [
                ("Treasuries", ["treasury", "yield", "curve", "auction"]),
                ("Fed", ["fed", "powell", "fomc"]),
            ],
            "credit": [
                ("IG", ["investment grade", "ig ", "lqd", "vcit"]),
                ("HY", ["high yield", "hy ", "hyg", "jnk"]),
                ("ETFs", ["etf", "fund flows", "bond fund"]),
            ],
            "macro": [
                ("Inflation", ["inflation", "cpi", "pce"]),
                ("Labor", ["jobs", "payroll", "unemployment", "labor"]),
                ("Policy", ["fed", "rates", "central bank"]),
            ],
        }
        for label, keywords in keyword_map.get(bucket, []):
            if any(keyword in title_lower for keyword in keywords):
                return label
        fallback = {"rates": "Rates", "credit": "Credit", "macro": "Macro"}
        return fallback.get(bucket, "News")

    def _load_snapshot_values(self) -> dict[str, dict]:
        latest = cached_latest_feature_values(
            app_cache_key(self.macro_feature_store.engine),
            tuple(sorted(self.SNAPSHOT_FEATURES)),
            self.macro_feature_store,
        )
        if latest.empty:
            return {}

        snapshot: dict[str, dict] = {}
        for _, row in latest.iterrows():
            feature_name = str(row["feature_name"])
            if feature_name not in self.SNAPSHOT_FEATURES:
                continue
            label, formatter = self.SNAPSHOT_FEATURES[feature_name]
            value = float(row["value"])
            if feature_name == "UST_2S10S":
                value = value * 100.0
            snapshot[feature_name] = {
                "label": label,
                "value": formatter.format(value),
                "date": pd.to_datetime(row["date"]).strftime("%Y-%m-%d"),
            }
        return snapshot

    def _render_snapshot_bar(self) -> None:
        snapshot = self._load_snapshot_values()
        if not snapshot:
            return

        columns = st.columns(len(self.SNAPSHOT_FEATURES))
        for column, feature_name in zip(columns, self.SNAPSHOT_FEATURES, strict=False):
            item = snapshot.get(feature_name)
            label = self.SNAPSHOT_FEATURES[feature_name][0]
            with column:
                st.markdown(
                    (
                        "<div style='border:1px solid #20252E;background:#050505;padding:0.40rem 0.55rem;"
                        "border-radius:2px;margin-bottom:0.45rem;'>"
                        f"<div style='color:#8D877B;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.45px;'>{label}</div>"
                        f"<div style='color:#F3F0E8;font-size:0.96rem;font-weight:700;margin-top:0.12rem;'>{item['value'] if item else 'n/a'}</div>"
                        f"<div style='color:#6F6A61;font-size:0.72rem;margin-top:0.08rem;'>{item['date'] if item else ''}</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

    def _render_event_watch(self) -> None:
        columns = st.columns(len(self.EVENT_WATCH))
        for column, (label, body) in zip(columns, self.EVENT_WATCH, strict=False):
            with column:
                st.markdown(
                    (
                        "<div style='border:1px solid #20252E;background:#050505;padding:0.38rem 0.55rem;"
                        "border-radius:2px;margin-bottom:0.55rem;'>"
                        f"<div style='color:#8D877B;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.45px;'>{label}</div>"
                        f"<div style='color:#B8B1A3;font-size:0.82rem;margin-top:0.10rem;'>{body}</div>"
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )

    def _render_featured_headline(self, title: str, items: list[dict], *, accent_color: str, bucket: str) -> None:
        if not items:
            self.info_panel.render_note(
                title=title,
                body="No headlines were returned for this feed right now.",
                accent_color=accent_color,
            )
            return

        featured = items[0]
        tag = self._headline_tag(featured["title"], bucket)
        body = (
            f"<span style='display:inline-block;padding:0.12rem 0.34rem;border:1px solid {accent_color};"
            f"color:{accent_color};font-size:0.68rem;text-transform:uppercase;margin-bottom:0.45rem;'>{tag}</span><br>"
            f"<a href='{featured['link']}' target='_blank' class='{self._news_link_class(bucket)}' "
            f"style='{self._news_link_style(font_size='0.95rem')}' "
            f" rel='noopener noreferrer'>"
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

    def _render_headline_list(self, items: list[dict], *, bucket: str, accent_color: str, max_items: int = 4) -> None:
        if len(items) <= 1:
            return

        rows = []
        for item in items[1:max_items + 1]:
            tag = self._headline_tag(item["title"], bucket)
            rows.append(
                f"<div style='padding:0.38rem 0;border-bottom:1px solid #1A1A1A;'>"
                f"<span style='display:inline-block;padding:0.10rem 0.28rem;border:1px solid {accent_color};"
                f"color:{accent_color};font-size:0.64rem;text-transform:uppercase;margin-bottom:0.25rem;'>{tag}</span><br>"
                f"<a href='{item['link']}' target='_blank' class='{self._news_link_class(bucket)}' style='{self._news_link_style(font_size='0.92rem', weight=500)}' "
                f" rel='noopener noreferrer'>"
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
        self._render_news_link_styles()
        with timed_block("news.load_feeds"):
            feed_data, feed_error = load_news_feeds()
        with timed_block("news.dedupe_feeds"):
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
        with timed_block("news.snapshot_bar"):
            self._render_snapshot_bar()
        self._render_event_watch()

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
                    f"<a href='{top_story['link']}' target='_blank' class='{self._news_link_class(top_story_bucket or 'credit')}' "
                    f"style='{self._news_link_style(font_size='1.08rem', line_height='1.45')}' "
                    f" rel='noopener noreferrer'>"
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
            self._render_featured_headline("Rates", rates_items, accent_color="#5DA9E9", bucket="rates")
            self._render_headline_list(rates_items, bucket="rates", accent_color="#5DA9E9")
        with col2:
            self._render_featured_headline("Credit And ETFs", credit_items, accent_color="#FF9F1A", bucket="credit")
            self._render_headline_list(credit_items, bucket="credit", accent_color="#FF9F1A")
        with col3:
            self._render_featured_headline("Macro", macro_items, accent_color="#FF5A36", bucket="macro")
            self._render_headline_list(macro_items, bucket="macro", accent_color="#FF5A36")

        st.markdown("### Coverage Map")
        coverage_col1, coverage_col2, coverage_col3 = st.columns(3)
        with coverage_col1:
            self.info_panel.render(
                title="Rates",
                headline="Curve, auctions, and policy tone",
                body="This section tracks front-end, belly, and long-end rate moves, Treasury supply, and Fed-sensitive market pricing.",
                margin_top="0.10rem",
                margin_bottom="0.20rem",
                accent_color="#5DA9E9",
            )
        with coverage_col2:
            self.info_panel.render(
                title="Credit And ETFs",
                headline="Spreads, flows, and implementation",
                body="This section combines IG and HY spread tone with bond ETF flows, liquidity, creation-redemption activity, and allocator positioning.",
                margin_top="0.10rem",
                margin_bottom="0.20rem",
                accent_color="#FF9F1A",
            )
        with coverage_col3:
            self.info_panel.render(
                title="Macro",
                headline="Inflation, labor, and policy backdrop",
                body="This section focuses on inflation prints, labor data, central-bank communication, and the broader macro narrative shaping fixed income.",
                margin_top="0.10rem",
                margin_bottom="0.20rem",
                accent_color="#FF5A36",
            )
