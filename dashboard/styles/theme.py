import streamlit as st


def apply_dashboard_theme():
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
            padding-bottom: 1.2rem;
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

        [data-baseweb="tab-list"] {
            gap: 0.35rem;
            margin-top: 0.30rem;
            margin-bottom: 0.55rem;
        }

        [data-baseweb="tab"] {
            background-color: #080808 !important;
            border: 1px solid #2A2A2A !important;
            border-radius: 1px !important;
            color: #9E988C !important;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.45px;
            padding: 0.45rem 0.80rem !important;
        }

        [aria-selected="true"][data-baseweb="tab"] {
            color: #FF9F1A !important;
            border-color: #FF9F1A !important;
            background-color: #101010 !important;
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

        .bb-highlight-metric {
            padding: 0.1rem 0 0.35rem 0;
        }

        .bb-highlight-metric-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            color: rgba(243, 240, 232, 0.75);
            margin-bottom: 0.2rem;
        }

        .bb-highlight-metric-value {
            font-size: 2rem;
            font-weight: 600;
            line-height: 1.1;
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

        @media (max-width: 900px) {
            .main .block-container {
                padding-left: 0.9rem;
                padding-right: 0.9rem;
                padding-bottom: 1rem;
            }

            div[data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.55rem !important;
            }

            div[data-testid="column"] {
                min-width: calc(50% - 0.55rem) !important;
                flex: 1 1 calc(50% - 0.55rem) !important;
            }

            div.stButton > button,
            div[data-baseweb="select"] > div,
            div[data-baseweb="input"] > div,
            [data-testid="stDateInputField"] {
                min-height: 44px !important;
            }

            .bb-header-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 640px) {
            .main .block-container {
                padding-top: 0.45rem;
                padding-left: 0.65rem;
                padding-right: 0.65rem;
                padding-bottom: 0.85rem;
            }

            h1 {
                font-size: 1.55rem !important;
            }

            h2, h3 {
                font-size: 1.0rem !important;
            }

            div[data-testid="column"] {
                min-width: 100% !important;
                flex: 1 1 100% !important;
            }

            div.stButton > button {
                width: 100% !important;
                font-size: 0.85rem !important;
                padding: 0.55rem 0.6rem !important;
            }

            [data-testid="stMetricLabel"] {
                font-size: 0.70rem !important;
            }

            [data-testid="stMetricValue"] {
                font-size: 1.15rem !important;
            }

            .bb-highlight-metric-label {
                font-size: 0.7rem;
            }

            .bb-highlight-metric-value {
                font-size: 1.45rem;
            }

            .bb-header-grid {
                grid-template-columns: 1fr;
            }

            .bb-header-cell {
                min-height: auto;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
