APP_CSS = """
<style>
.stApp {
    background-color: #000000;
    color: #F4F1DE;
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.block-container {
    padding-top: 0.6rem;
    padding-bottom: 1rem;
    max-width: 98%;
}
h1, h2, h3 {
    color: #FF9F1A;
    letter-spacing: 0.6px;
    font-weight: 700;
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    text-transform: uppercase;
    margin-bottom: 0.35rem;
}
p, label, div, span, li {
    color: #F4F1DE;
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
[data-testid="stDateInputField"] {
    background-color: #111111 !important;
    border: 1px solid #FF9F1A !important;
    border-radius: 2px !important;
    color: #F4F1DE !important;
    box-shadow: none !important;
}
div.stNumberInput > div,
div.stTextArea > div {
    background-color: transparent !important;
}
div.stNumberInput input,
textarea,
input {
    background-color: #111111 !important;
    color: #F4F1DE !important;
    border-radius: 2px !important;
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
div.stButton > button {
    background-color: #111111 !important;
    color: #FF9F1A !important;
    border: 1px solid #FF9F1A !important;
    border-radius: 2px !important;
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
    text-transform: uppercase;
}
div.stButton > button:hover {
    background-color: #1A1A1A !important;
    color: #FFD166 !important;
    border-color: #FFD166 !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid #FF9F1A;
    border-radius: 2px;
    overflow: hidden;
}
.bb-panel {
    border: 1px solid #FF9F1A;
    background-color: #050505;
    padding: 0.55rem 0.7rem;
    margin-bottom: 0.75rem;
    border-radius: 2px;
}
.bb-header-grid {
    display: grid;
    grid-template-columns: 1.2fr repeat(5, 1fr);
    gap: 0.45rem;
    align-items: stretch;
}
.bb-header-cell {
    border: 1px solid #2A2A2A;
    background-color: #0B0B0B;
    padding: 0.45rem 0.55rem;
    min-height: 58px;
}
.bb-header-label {
    color: #BFB8A5;
    font-size: 0.72rem;
    text-transform: uppercase;
    margin-bottom: 0.18rem;
}
.bb-header-value {
    color: #F4F1DE;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.15;
}
.bb-pos { color: #00C176 !important; }
.bb-neg { color: #FF5A36 !important; }
.stCaption {
    color: #BFB8A5 !important;
    font-family: "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}
</style>
"""
