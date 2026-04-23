import streamlit as st


def apply_dashboard_theme():
    st.markdown(
        """
        <style>
        .stApp {
            background:
                linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px),
                radial-gradient(circle at top right, rgba(0, 173, 181, 0.05), transparent 22%),
                radial-gradient(circle at 18% 10%, rgba(255, 159, 26, 0.05), transparent 18%),
                #000000;
            background-size: 24px 24px, 24px 24px, auto, auto, auto;
            color: #F3F0E8;
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                repeating-linear-gradient(
                    to bottom,
                    rgba(255,255,255,0.015) 0px,
                    rgba(255,255,255,0.015) 1px,
                    transparent 1px,
                    transparent 4px
                );
            opacity: 0.08;
            mix-blend-mode: screen;
            z-index: 0;
        }

        html, body, [class*="css"] {
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .main .block-container {
            max-width: 98% !important;
            padding-top: 0.38rem;
            padding-left: 0.95rem;
            padding-right: 0.95rem;
            padding-bottom: 1rem;
            position: relative;
            z-index: 1;
        }

        h1, h2, h3 {
            color: #FF9F1A !important;
            font-weight: 700 !important;
            text-transform: uppercase;
            letter-spacing: 0.42px;
            margin-bottom: 0.18rem !important;
        }

        p, span, label, div {
            color: #F3F0E8;
        }

        .stCaption {
            color: #B8B1A3 !important;
        }

        .app-shell-brand {
            display: flex;
            align-items: baseline;
            gap: 0.7rem;
            padding: 0.02rem 0 0.22rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 0.18rem;
        }

        .app-shell-title {
            color: #F3F0E8;
            font-size: 1.3rem;
            font-weight: 700;
            letter-spacing: 0.25px;
            text-transform: uppercase;
        }

        .app-shell-title span {
            color: #FF9F1A;
        }

        .app-shell-subtitle {
            color: #9E988C;
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.55px;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        [data-testid="stDateInputField"] {
            background-color: #090A0B !important;
            border: 1px solid #1A1E24 !important;
            border-radius: 0 !important;
            color: #F3F0E8 !important;
            box-shadow: none !important;
            min-height: 30px !important;
        }

        input, textarea {
            background-color: #090A0B !important;
            color: #F3F0E8 !important;
            border-radius: 0 !important;
            font-size: 0.82rem !important;
        }

        div.stButton > button {
            background-color: transparent !important;
            color: #A9A292 !important;
            border: 1px solid transparent !important;
            border-radius: 0 !important;
            text-transform: uppercase;
            font-weight: 600;
            min-height: 28px !important;
            font-size: 0.74rem !important;
            letter-spacing: 0.45px !important;
            padding: 0.1rem 0.35rem !important;
            box-shadow: none !important;
        }

        div.stButton > button:hover {
            background-color: rgba(255,255,255,0.03) !important;
            color: #F3F0E8 !important;
            border-color: transparent !important;
        }

        div.stButton > button[kind="primary"] {
            background: transparent !important;
            color: #FF9F1A !important;
            border-bottom: 2px solid #FF9F1A !important;
            font-weight: 700 !important;
            text-shadow: 0 0 6px rgba(255,159,26,0.22);
        }

        div.stButton > button[kind="primary"]:hover {
            color: #FFD166 !important;
            border-bottom-color: #FFD166 !important;
            box-shadow: none !important;
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

        .bb-summary-strip {
            border: 1px solid #2A2A2A;
            background-color: #050505;
            padding: 0.45rem 0.55rem;
            margin: 0.2rem 0 0.75rem 0;
            border-radius: 2px;
        }

        .bb-summary-grid {
            display: grid;
            grid-template-columns: 1.15fr 1fr 1fr 1fr 1.15fr 0.95fr 0.95fr 0.95fr;
            gap: 0.4rem;
            align-items: stretch;
        }

        .bb-summary-cell {
            border: 1px solid #2A2A2A;
            background: #0A0A0A;
            padding: 0.42rem 0.55rem;
            min-height: 68px;
            overflow-wrap: anywhere;
        }

        .bb-summary-cell--primary {
            box-shadow: inset 0 0 0 1px rgba(255,159,26,0.20);
        }

        .bb-summary-label {
            color: #B8B1A3;
            font-size: 0.68rem;
            text-transform: uppercase;
            margin-bottom: 0.16rem;
            letter-spacing: 0.35px;
        }

        .bb-summary-value {
            color: #F3F0E8;
            font-size: 0.92rem;
            font-weight: 700;
            line-height: 1.22;
            word-break: break-word;
        }

        .bb-summary-value--primary {
            font-size: 1.12rem;
            font-weight: 800;
        }

        .bb-metric-group-spacer {
            height: 0.45rem;
        }

        .bb-regime-badge {
            display: inline-block;
            padding: 0.16rem 0.42rem;
            font-size: 0.72rem;
            text-transform: uppercase;
            max-width: 100%;
            white-space: normal;
            line-height: 1.25;
        }

        .bb-macro-card-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.55rem;
            margin-bottom: 0.75rem;
        }

        .bb-macro-card {
            border: 1px solid #2A2A2A;
            background: #050505;
            padding: 0.55rem 0.65rem 0.6rem 0.65rem;
            min-height: 132px;
        }

        .bb-macro-card-label {
            color: #F3F0E8;
            font-size: 0.82rem;
            text-transform: uppercase;
            line-height: 1.2;
            margin-bottom: 0.3rem;
        }

        .bb-macro-card-value {
            color: #F3F0E8;
            font-size: 1.85rem;
            font-weight: 700;
            line-height: 1.05;
            margin-bottom: 0.4rem;
        }

        .bb-macro-card-delta {
            color: #B8B1A3;
            font-size: 0.92rem;
            margin-bottom: 0.2rem;
        }

        .bb-macro-card-delta--positive {
            color: #00C176;
        }

        .bb-macro-card-delta--negative {
            color: #FF5A36;
        }

        .bb-macro-card-delta--neutral {
            color: #B8B1A3;
        }

        .bb-highlight-metric {
            padding: 0.1rem 0 0.55rem 0;
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

        .home-market-strip {
            display: grid;
            grid-template-columns: 1.2fr repeat(7, minmax(0, 1fr));
            gap: 0;
            border: 1px solid #1A1E24;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)),
                rgba(5, 7, 8, 0.98);
            margin: 0.08rem 0 0.38rem 0;
            overflow: hidden;
            border-radius: 0;
        }

        .home-strip-primary,
        .home-strip-cell {
            padding: 0.45rem 0.6rem;
            border-right: 1px solid #1A1E24;
            min-height: 56px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        .home-strip-kicker,
        .home-panel-kicker,
        .home-section-title {
            color: #FF9F1A;
            text-transform: uppercase;
            letter-spacing: 0.42px;
            font-size: 0.68rem;
            font-weight: 700;
        }

        .home-strip-kicker::before {
            content: "●";
            color: #FF9F1A;
            margin-right: 0.35rem;
            font-size: 0.56rem;
            text-shadow: 0 0 6px rgba(255,159,26,0.55);
            animation: homePulse 1.8s ease-in-out infinite;
        }

        .home-section-title {
            margin: 0.45rem 0 0.2rem 0;
        }

        .home-strip-sub {
            color: #9E988C;
            font-size: 0.74rem;
            margin-top: 0.14rem;
        }

        .home-strip-label {
            color: #B8B1A3;
            text-transform: uppercase;
            font-size: 0.62rem;
            margin-bottom: 0.08rem;
            letter-spacing: 0.3px;
        }

        .home-strip-mini {
            color: #7E7A72;
            text-transform: uppercase;
            font-size: 0.54rem;
            letter-spacing: 0.28px;
            margin-bottom: 0.08rem;
        }

        .home-live-chip {
            display: inline-block;
            margin-left: 0.35rem;
            color: #F3F0E8;
            font-size: 0.52rem;
            letter-spacing: 0.34px;
            padding: 0.05rem 0.2rem;
            border: 1px solid rgba(255,159,26,0.35);
            vertical-align: middle;
        }

        .home-strip-value {
            color: #F3F0E8;
            font-size: 0.95rem;
            font-weight: 700;
            margin-bottom: 0.06rem;
            letter-spacing: 0.1px;
        }

        .home-strip-value-row {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 0.4rem;
        }

        .home-strip-delta {
            font-size: 0.74rem;
            font-weight: 600;
            white-space: nowrap;
        }

        .home-delta-up {
            color: #00C176 !important;
        }

        .home-delta-down {
            color: #FF5A36 !important;
        }

        .home-delta-flat {
            color: #9E988C !important;
        }

        .home-hero {
            min-height: 220px;
            border: 1px solid #1A1E24;
            border-radius: 0;
            background:
                linear-gradient(180deg, rgba(6,7,8,0.98), rgba(3,3,4,0.96)),
                radial-gradient(circle at 82% 50%, rgba(0,173,181,0.10), transparent 30%);
            padding: 1rem 1.1rem 0.9rem 1.1rem;
            display: grid;
            grid-template-columns: 0.85fr 1.15fr;
            gap: 0.45rem;
            overflow: hidden;
            position: relative;
        }

        .home-eyebrow {
            color: #00D5E6;
            text-transform: uppercase;
            letter-spacing: 0.55px;
            font-size: 0.65rem;
            margin-bottom: 0.32rem;
        }

        .home-hero-title {
            color: #F7F3EA;
            font-size: 1.85rem;
            font-weight: 700;
            line-height: 1.04;
            margin-bottom: 0.42rem;
            max-width: 420px;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-hero-body {
            color: #C9C1B2;
            font-size: 0.9rem;
            line-height: 1.45;
            max-width: 390px;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-decision-strip {
            margin-top: 0.42rem;
            padding-top: 0.32rem;
            border-top: 1px solid rgba(255,255,255,0.08);
            max-width: 390px;
        }

        .home-decision-label {
            color: #8A857A;
            text-transform: uppercase;
            font-size: 0.58rem;
            letter-spacing: 0.34px;
            margin-bottom: 0.08rem;
        }

        .home-decision-value {
            color: #F3F0E8;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.1px;
        }

        .home-tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.22rem;
            margin-top: 0.34rem;
        }

        .home-tag-row--tight {
            margin-top: 0.14rem;
            margin-bottom: 0.18rem;
        }

        .home-signal-tag {
            display: inline-flex;
            align-items: center;
            padding: 0.08rem 0.24rem;
            border: 1px solid #232830;
            color: #C9C1B2;
            background: rgba(255,255,255,0.02);
            text-transform: uppercase;
            font-size: 0.56rem;
            letter-spacing: 0.34px;
            line-height: 1.1;
        }

        .home-signal-tag--alert {
            color: #FF9F1A;
            border-color: rgba(255,159,26,0.28);
            box-shadow: inset 0 0 6px rgba(255,159,26,0.06);
        }

        .home-hero-canvas {
            position: relative;
            min-height: 180px;
            border-radius: 0;
            background-color: transparent;
            background-size: 100% 100%;
            background-position: center center;
            background-repeat: no-repeat;
            overflow: hidden;
            border: 0;
        }

        .home-regime-card,
        .home-side-card,
        .home-wide-card,
        .home-built-card {
            border: 1px solid #1A1E24;
            border-radius: 0;
            background: linear-gradient(180deg, rgba(6,6,6,0.96), rgba(4,4,4,0.96));
            padding: 0.7rem 0.78rem;
            min-height: 100%;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
        }

        .home-regime-label {
            font-size: 1.45rem;
            font-weight: 700;
            margin: 0.34rem 0 0.28rem 0;
        }

        .home-regime-body,
        .home-side-body,
        .home-wide-body,
        .home-built-body {
            color: #C1BAAC;
            line-height: 1.42;
            font-size: 0.82rem;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-regime-scale {
            position: relative;
            height: 8px;
            margin: 0.65rem 0 0.32rem 0;
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(255,90,54,0.95), rgba(255,209,102,0.65) 50%, rgba(0,193,118,0.95));
        }

        .home-regime-scale-bar {
            position: absolute;
            inset: 0;
            border-radius: 999px;
            opacity: 0.55;
        }

        .home-regime-scale-marker {
            position: absolute;
            top: -2px;
            width: 10px;
            height: 12px;
            border-radius: 999px;
            background: #F3F0E8;
            box-shadow: 0 0 0 2px rgba(0,0,0,0.7);
        }

        .home-regime-legend {
            display: flex;
            justify-content: space-between;
            color: #9E988C;
            text-transform: uppercase;
            font-size: 0.58rem;
        }

        .home-stat-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.45rem;
            margin-top: 0.28rem;
            margin-bottom: 0.36rem;
        }

        .home-stat-card {
            border: 1px solid #1A1E24;
            border-radius: 0;
            background: rgba(6,6,6,0.96);
            padding: 0.58rem 0.62rem;
            display: grid;
            grid-template-columns: 34px 1fr;
            gap: 0.55rem;
            align-items: center;
        }

        .home-stat-icon {
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 0;
            background: linear-gradient(145deg, rgba(255,159,26,0.14), rgba(255,159,26,0.03));
            color: #FF9F1A;
            font-size: 0.95rem;
            font-weight: 700;
        }

        .home-stat-icon svg {
            width: 22px;
            height: 22px;
            display: block;
            color: inherit;
            fill: currentColor;
        }

        .home-stat-label {
            color: #B8B1A3;
            text-transform: uppercase;
            font-size: 0.6rem;
            margin-bottom: 0.08rem;
            letter-spacing: 0.28px;
        }

        .home-stat-value {
            color: #F7F3EA;
            font-size: 1.45rem;
            line-height: 1.02;
            font-weight: 700;
        }

        .home-stat-value--date {
            font-size: 1.08rem;
        }

        .home-stat-note {
            color: #9E988C;
            font-size: 0.7rem;
            margin-top: 0.1rem;
        }

        .home-side-title,
        .home-wide-title,
        .home-built-title {
            color: #F7F3EA;
            font-size: 1.02rem;
            font-weight: 700;
            line-height: 1.15;
            margin: 0.2rem 0 0.3rem 0;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-pulse-list {
            margin-top: 0.45rem;
            display: grid;
            gap: 0.28rem;
        }

        .home-pulse-row {
            display: grid;
            grid-template-columns: 16px 1fr auto;
            gap: 0.32rem;
            align-items: start;
            padding-top: 0.18rem;
            border-top: 1px solid rgba(255,255,255,0.04);
        }

        .home-pulse-icon {
            color: #FF9F1A;
            font-size: 0.75rem;
            line-height: 1.2;
        }

        .home-pulse-text {
            color: #C1BAAC;
            line-height: 1.34;
            font-size: 0.76rem;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-pulse-tag {
            text-transform: uppercase;
            font-size: 0.58rem;
            letter-spacing: 0.34px;
            padding-top: 0.02rem;
            white-space: nowrap;
        }

        .home-pulse-tag--elevated,
        .home-pulse-tag--active {
            color: #FF9F1A;
        }

        .home-pulse-tag--mixed {
            color: #FFD166;
        }

        .home-pulse-tag--neutral {
            color: #9E988C;
        }

        .home-context-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.45rem;
            margin-bottom: 0.34rem;
        }

        .home-context-card {
            border: 1px solid #1A1E24;
            border-radius: 0;
            background: linear-gradient(180deg, rgba(6,6,6,0.96), rgba(4,4,4,0.96));
            padding: 0.72rem 0.78rem;
            min-height: 100%;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
        }

        .home-context-title {
            color: #F7F3EA;
            font-size: 0.98rem;
            font-weight: 700;
            line-height: 1.2;
            margin: 0.24rem 0 0.34rem 0;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-context-body {
            color: #C1BAAC;
            line-height: 1.48;
            font-size: 0.78rem;
            font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        }

        .home-wide-card {
            margin-top: 0.04rem;
            margin-bottom: 0.28rem;
        }

        .home-inline-regime {
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.22px;
            text-shadow: 0 0 6px rgba(255,159,26,0.18);
        }

        .home-wide-body--compact {
            display: grid;
            gap: 0.1rem;
        }

        .home-inline-link,
        a.home-inline-link,
        a.home-inline-link:visited,
        a.home-inline-link:hover,
        a.home-inline-link:active {
            margin-top: 0.28rem;
            color: #FF9F1A;
            text-transform: uppercase;
            font-size: 0.62rem;
            letter-spacing: 0.34px;
            text-shadow: 0 0 4px rgba(255,159,26,0.18);
            text-decoration: none;
            display: inline-block;
        }

        .home-inline-link--small {
            margin-top: 0.32rem;
            font-size: 0.58rem;
        }

        .home-built-card {
            min-height: 100%;
            display: grid;
            grid-template-columns: 54px 1fr;
            gap: 0.65rem;
            align-items: start;
            margin-top: 0.3rem;
            background:
                radial-gradient(circle at bottom right, rgba(0,173,181,0.08), transparent 30%),
                linear-gradient(180deg, rgba(6,6,6,0.96), rgba(4,4,4,0.96));
        }

        .home-built-icon {
            width: 54px;
            height: 54px;
            border-radius: 0;
            background: rgba(6,18,24,0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #00D5E6;
            font-size: 1.2rem;
            border: 1px solid rgba(0,213,230,0.12);
        }

        .home-table-up {
            color: #00C176;
            font-weight: 700;
        }

        .home-table-down {
            color: #FF5A36;
            font-weight: 700;
        }

        .home-table-flat {
            color: #B8B1A3;
            font-weight: 600;
        }

        .home-table-note {
            color: #8A857A;
            font-size: 0.62rem;
            text-transform: uppercase;
            letter-spacing: 0.24px;
            margin-left: 0.15rem;
        }

        @keyframes homePulse {
            0%, 100% { opacity: 0.65; }
            50% { opacity: 1; }
        }

        hr {
            border: none;
            border-top: 1px solid #1F1F1F;
            margin: 0.28rem 0 0.42rem 0;
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

            .bb-summary-grid {
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }

            .bb-macro-card-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .home-market-strip {
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }

            .home-hero {
                grid-template-columns: 1fr;
                min-height: auto;
            }

            .home-stat-grid {
                grid-template-columns: 1fr;
            }

            .home-context-grid {
                grid-template-columns: 1fr;
            }

            .home-built-card {
                grid-template-columns: 1fr;
                margin-top: 1rem;
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

            .bb-summary-strip {
                padding: 0.42rem 0.48rem;
                margin-bottom: 0.9rem;
            }

            .bb-summary-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.5rem;
            }

            .bb-summary-cell {
                min-height: auto;
                padding: 0.48rem 0.55rem;
            }

            .bb-summary-label {
                font-size: 0.62rem;
            }

            .bb-summary-value {
                font-size: 0.84rem;
            }

            .bb-summary-value--primary {
                font-size: 1.0rem;
            }

            .bb-metric-group-spacer {
                height: 0.65rem;
            }

            .bb-macro-card-grid {
                grid-template-columns: 1fr;
                gap: 0.65rem;
                margin-bottom: 0.95rem;
            }

            .bb-macro-card {
                min-height: auto;
                padding: 0.58rem 0.65rem 0.65rem 0.65rem;
            }

            .bb-macro-card-label {
                font-size: 0.8rem;
                margin-bottom: 0.32rem;
            }

            .bb-macro-card-value {
                font-size: 1.65rem;
                margin-bottom: 0.46rem;
            }

            .bb-macro-card-delta {
                font-size: 0.9rem;
                margin-bottom: 0.28rem;
            }

            .bb-regime-badge {
                display: block;
                width: fit-content;
            }

            .app-shell-brand {
                flex-direction: column;
                gap: 0.25rem;
                align-items: flex-start;
            }

            .home-market-strip {
                grid-template-columns: 1fr;
            }

            .home-strip-primary,
            .home-strip-cell {
                border-right: none;
                border-bottom: 1px solid rgba(255,255,255,0.08);
                min-height: auto;
            }

            .home-hero-title {
                font-size: 2.2rem;
            }

            .home-hero-body {
                font-size: 0.98rem;
            }

            .home-regime-label {
                font-size: 1.6rem;
            }

            .home-side-title,
            .home-wide-title,
            .home-built-title {
                font-size: 1.2rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
