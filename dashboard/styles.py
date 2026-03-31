import streamlit as st


def apply_bloomberg_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #000000;
            color: #F3F0E8;
        }

        html, body, [class*="css"] {
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .main .block-container {
            max-width: 98% !important;
            padding-top: 0.6rem;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
            padding-bottom: 1rem;
        }

        h1, h2, h3 {
            color: #FF9F1A !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-bottom: 0.35rem !important;
        }

        p, span, label, div {
            color: #F3F0E8;
        }

        .stCaption {
            color: #B8B1A3 !important;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        [data-testid="stDateInputField"] {
            background-color: #0A0A0A !important;
            border: 1px solid #FF9F1A !important;
            border-radius: 1px !important;
            color: #F3F0E8 !important;
            box-shadow: none !important;
            min-height: 38px !important;
        }

        input, textarea {
            background-color: #0A0A0A !important;
            color: #F3F0E8 !important;
            border-radius: 1px !important;
        }

        div.stButton > button {
            background-color: #0A0A0A !important;
            color: #FF9F1A !important;
            border: 1px solid #FF9F1A !important;
            border-radius: 1px !important;
            text-transform: uppercase;
            font-weight: 600;
        }

        div.stButton > button:hover {
            background-color: #121212 !important;
            color: #FFD166 !important;
            border-color: #FFD166 !important;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid #2B2B2B !important;
            border-radius: 1px !important;
        }

        .bb-panel {
            border: 1px solid #2A2A2A;
            background-color: #050505;
            padding: 0.55rem 0.7rem;
            margin-bottom: 0.75rem;
            border-radius: 1px;
        }

        .bb-header-grid {
            display: grid;
            grid-template-columns: 1.2fr repeat(5, 1fr);
            gap: 0.4rem;
            align-items: stretch;
        }

        .bb-header-cell {
            border: 1px solid #2A2A2A;
            background-color: #0A0A0A;
            padding: 0.40rem 0.50rem;
            min-height: 56px;
        }

        .bb-header-label {
            color: #B8B1A3;
            font-size: 0.68rem;
            text-transform: uppercase;
            margin-bottom: 0.15rem;
        }

        .bb-header-value {
            color: #F3F0E8;
            font-size: 0.96rem;
            font-weight: 700;
            line-height: 1.15;
        }

        .bb-pos {
            color: #00C176 !important;
        }

        .bb-neg {
            color: #FF5A36 !important;
        }

        hr {
            border: none;
            border-top: 1px solid #1F1F1F;
            margin: 0.6rem 0 0.8rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )