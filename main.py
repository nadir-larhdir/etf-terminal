import streamlit as st
from dashboard.dashboard_app import run_app

st.set_page_config(
    page_title="ETF Terminal",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    run_app()


if __name__ == "__main__":
    main()
