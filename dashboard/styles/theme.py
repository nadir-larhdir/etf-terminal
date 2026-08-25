"""Global CSS injection for the ETF Terminal dashboard theme."""

import streamlit as st

from dashboard.render import stylesheet


def apply_dashboard_theme() -> None:
    """Inject the terminal stylesheet into the active Streamlit page."""
    st.markdown(stylesheet("theme.css"), unsafe_allow_html=True)
