from db.connection import get_engine
from repositories.security_repository import SecurityRepository
from repositories.price_repository import PriceRepository
from repositories.input_repository import InputRepository
from dashboard.dashboard import Dashboard
import streamlit as st

st.set_page_config(
    page_title="ETF Monitor",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    engine = get_engine()
    security_repo = SecurityRepository(engine)
    price_repo = PriceRepository(engine)
    input_repo = InputRepository(engine)
    app = Dashboard(security_repo, price_repo, input_repo)
    app.run()


if __name__ == "__main__":
    main()
