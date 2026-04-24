import base64
from pathlib import Path

import streamlit as st
from PIL import Image
from dashboard.dashboard_app import run_app

APP_ICON = Path(__file__).parent / "dashboard" / "assets" / "favicon.png"
APP_ICON_DATA = base64.b64encode(APP_ICON.read_bytes()).decode("ascii")

st.set_page_config(
    page_title="ETF Terminal",
    page_icon=Image.open(APP_ICON),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    '<link rel="shortcut icon" href="data:image/png;base64,' + APP_ICON_DATA + '#v=2">',
    unsafe_allow_html=True,
)


def main():
    run_app()


if __name__ == "__main__":
    main()
