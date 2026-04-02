import streamlit as st


class InfoPanel:
    """Render reusable narrative panels with the dashboard's terminal-style theme."""

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
        footer_block = ""
        if footer:
            footer_block = (
                f"<div style='"
                f"color:{body_color};"
                f"font-size:0.80rem;"
                f"line-height:1.40;"
                f"margin-top:0.35rem;"
                f"padding-top:0.30rem;"
                f"border-top:1px solid {border_color};"
                f"'>"
                f"{footer}"
                f"</div>"
            )

        html = (
            f"<div style='"
            f"border:1px solid {border_color};"
            f"background-color:{background_color};"
            f"padding:0.60rem 0.75rem;"
            f"border-radius:2px;"
            f"margin-top:{margin_top};"
            f"margin-bottom:{margin_bottom};"
            f"box-shadow:inset 0 0 0 1px rgba(255,255,255,0.01);"
            f"'>"

            f"<div style='"
            f"color:{accent_color};"
            f"font-size:0.72rem;"
            f"text-transform:uppercase;"
            f"letter-spacing:0.45px;"
            f"margin-bottom:0.18rem;"
            f"font-weight:700;"
            f"'>"
            f"{title}"
            f"</div>"

            f"<div style='"
            f"color:{headline_color};"
            f"font-size:0.98rem;"
            f"font-weight:700;"
            f"margin-bottom:0.22rem;"
            f"line-height:1.35;"
            f"'>"
            f"{headline}"
            f"</div>"

            f"<div style='"
            f"color:{body_color};"
            f"font-size:0.88rem;"
            f"line-height:1.52;"
            f"'>"
            f"{body}"
            f"</div>"

            f"{footer_block}"
            f"</div>"
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
        html = (
            f"<div style='"
            f"border:1px solid {border_color};"
            f"background-color:{background_color};"
            f"padding:0.50rem 0.70rem;"
            f"border-radius:2px;"
            f"margin-top:{margin_top};"
            f"margin-bottom:{margin_bottom};"
            f"'>"

            f"<div style='"
            f"color:{accent_color};"
            f"font-size:0.70rem;"
            f"text-transform:uppercase;"
            f"letter-spacing:0.45px;"
            f"margin-bottom:0.15rem;"
            f"font-weight:700;"
            f"'>"
            f"{title}"
            f"</div>"

            f"<div style='"
            f"color:{body_color};"
            f"font-size:0.84rem;"
            f"line-height:1.45;"
            f"'>"
            f"{body}"
            f"</div>"

            f"</div>"
        )

        st.markdown(html, unsafe_allow_html=True)
