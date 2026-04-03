import streamlit as st


class InfoPanel:
    """Render reusable narrative panels with the dashboard's terminal-style theme."""

    def _panel_html(
        self,
        title: str,
        body: str,
        *,
        headline: str | None = None,
        footer: str | None = None,
        accent_color: str,
        headline_color: str,
        body_color: str,
        background_color: str,
        border_color: str,
        padding: str,
        title_font_size: str,
        body_font_size: str,
        margin_top: str,
        margin_bottom: str,
        box_shadow: bool = False,
    ) -> str:
        headline_block = ""
        if headline:
            headline_block = (
                f"<div style='color:{headline_color};font-size:0.98rem;font-weight:700;"
                f"margin-bottom:0.22rem;line-height:1.35;'>{headline}</div>"
            )

        footer_block = ""
        if footer:
            footer_block = (
                f"<div style='color:{body_color};font-size:0.80rem;line-height:1.40;"
                f"margin-top:0.35rem;padding-top:0.30rem;border-top:1px solid {border_color};'>"
                f"{footer}</div>"
            )

        shadow = "box-shadow:inset 0 0 0 1px rgba(255,255,255,0.01);" if box_shadow else ""
        return (
            f"<div style='border:1px solid {border_color};background-color:{background_color};"
            f"padding:{padding};border-radius:2px;margin-top:{margin_top};margin-bottom:{margin_bottom};{shadow}'>"
            f"<div style='color:{accent_color};font-size:{title_font_size};text-transform:uppercase;"
            f"letter-spacing:0.45px;margin-bottom:0.18rem;font-weight:700;'>{title}</div>"
            f"{headline_block}"
            f"<div style='color:{body_color};font-size:{body_font_size};line-height:1.52;'>{body}</div>"
            f"{footer_block}</div>"
        )

    def render(
        self,
        title: str,
        headline: str,
        body: str,
        *,
        footer: str | None = None,
        accent_color: str = "#FF9F1A",
        headline_color: str = "#F3F0E8",
        body_color: str = "#B8B1A3",
        background_color: str = "#050505",
        border_color: str = "#2A2A2A",
        margin_top: str = "0.35rem",
        margin_bottom: str = "0.50rem",
    ) -> None:
        html = self._panel_html(
            title=title,
            headline=headline,
            body=body,
            footer=footer,
            accent_color=accent_color,
            headline_color=headline_color,
            body_color=body_color,
            background_color=background_color,
            border_color=border_color,
            padding="0.60rem 0.75rem",
            title_font_size="0.72rem",
            body_font_size="0.88rem",
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            box_shadow=True,
        )
        st.markdown(html, unsafe_allow_html=True)

    def render_note(
        self,
        title: str,
        body: str,
        *,
        accent_color: str = "#00ADB5",
        body_color: str = "#B8B1A3",
        background_color: str = "#050505",
        border_color: str = "#2A2A2A",
        margin_top: str = "0.20rem",
        margin_bottom: str = "0.40rem",
    ) -> None:
        html = self._panel_html(
            title=title,
            body=body,
            accent_color=accent_color,
            headline_color=body_color,
            body_color=body_color,
            background_color=background_color,
            border_color=border_color,
            padding="0.50rem 0.70rem",
            title_font_size="0.70rem",
            body_font_size="0.84rem",
            margin_top=margin_top,
            margin_bottom=margin_bottom,
        )
        st.markdown(html, unsafe_allow_html=True)
