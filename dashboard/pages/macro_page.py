"""Macro page: yield curve, feature cards, chart grid, and rule-based regime summaries."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.optimize import minimize

from dashboard.cache import app_cache_key, cached_feature_matrix
from dashboard.components import DashboardControls, InfoPanel
from dashboard.components.controls import WINDOW_LOOKBACK_MAP
from dashboard.mobile import PLOTLY_CHART_CONFIG, responsive_chart_layout
from dashboard.perf import timed_block

CARD_CONFIG = [
    ("10Y yield", "UST_10Y_LEVEL", "UST_10Y_Z20", "Rates"),
    ("2s10s", "UST_2S10S", "UST_2S10S_Z20", "Curve"),
    ("5s30s", "UST_5S30S", "UST_5S30S_Z20", "Curve"),
    ("5Y breakeven", "BEI_5Y", "BEI_5Y_Z20", "Inflation"),
    ("IG OAS", "IG_OAS_LEVEL", "IG_OAS_Z20", "Credit"),
    ("HY OAS", "HY_OAS_LEVEL", "HY_OAS_Z20", "Credit"),
    ("HY-IG spread", "HY_MINUS_IG_OAS", "HY_MINUS_IG_OAS_Z20", "Credit"),
    ("CPI YoY", "CPI_YOY", None, "Inflation"),
    ("Fed Funds", "FEDFUNDS_LEVEL", None, "Policy"),
    ("Unemployment rate", "UNRATE_LEVEL", None, "Growth"),
]

CHART_CONFIG = [
    ("Treasury yields", ["UST_2Y_LEVEL", "UST_10Y_LEVEL", "UST_30Y_LEVEL"]),
    ("Credit OAS", ["IG_OAS_LEVEL", "BBB_OAS_LEVEL", "HY_OAS_LEVEL"]),
    ("2s10s", ["UST_2S10S"]),
    ("5s30s", ["UST_5S30S"]),
    ("CPI YoY", ["CPI_YOY"]),
    ("5Y breakeven", ["BEI_5Y"]),
    ("HY minus IG OAS", ["HY_MINUS_IG_OAS"]),
    ("Real-rate proxy", ["REAL_RATE_PROXY"]),
    ("Fed Funds", ["FEDFUNDS_LEVEL"]),
    ("Unemployment", ["UNRATE_LEVEL"]),
]

YIELD_CURVE_CONFIG = [
    ("3M", 0.25, "UST_3M_LEVEL"),
    ("6M", 0.50, "UST_6M_LEVEL"),
    ("1Y", 1.00, "UST_1Y_LEVEL"),
    ("2Y", 2.00, "UST_2Y_LEVEL"),
    ("3Y", 3.00, "UST_3Y_LEVEL"),
    ("5Y", 5.00, "UST_5Y_LEVEL"),
    ("7Y", 7.00, "UST_7Y_LEVEL"),
    ("10Y", 10.00, "UST_10Y_LEVEL"),
    ("20Y", 20.00, "UST_20Y_LEVEL"),
    ("30Y", 30.00, "UST_30Y_LEVEL"),
]

FEATURE_LABELS = {
    "UST_2Y_LEVEL": "UST 2Y",
    "UST_10Y_LEVEL": "UST 10Y",
    "UST_30Y_LEVEL": "UST 30Y",
    "UST_2S10S": "UST 2s10s",
    "UST_5S30S": "UST 5s30s",
    "CPI_YOY": "CPI YoY",
    "BEI_5Y": "5Y Breakeven",
    "REAL_RATE_PROXY": "Real-Rate Proxy",
    "FEDFUNDS_LEVEL": "Fed Funds",
    "UNRATE_LEVEL": "Unemployment",
    "IG_OAS_LEVEL": "IG OAS",
    "HY_OAS_LEVEL": "HY OAS",
    "BBB_OAS_LEVEL": "BBB OAS",
    "HY_MINUS_IG_OAS": "HY-IG OAS",
}

OAS_FEATURES = {
    "IG_OAS_LEVEL",
    "HY_OAS_LEVEL",
    "BBB_OAS_LEVEL",
    "SINGLE_B_OAS_LEVEL",
    "HY_MINUS_IG_OAS",
    "BBB_MINUS_IG_OAS",
    "SINGLE_B_MINUS_HY_OAS",
}

PERCENT_LEVEL_FEATURES = {
    "UST_10Y_LEVEL",
    "UST_2S10S",
    "UST_5S30S",
    "BEI_5Y",
    "CPI_YOY",
    "FEDFUNDS_LEVEL",
    "UNRATE_LEVEL",
}

Z_SCORE_FEATURES = {
    "UST_10Y_Z20",
    "UST_2S10S_Z20",
    "UST_2S10S_Z60",
    "UST_5S30S_Z20",
    "BEI_5Y_Z20",
    "IG_OAS_Z20",
    "HY_OAS_Z20",
    "HY_MINUS_IG_OAS_Z20",
}

LOOKBACK_MAP = {**WINDOW_LOOKBACK_MAP, "5Y": 1260, "ALL": None}
CHART_PALETTE = ["#6F7B46", "#5F8D84", "#A55C45", "#4E7B52"]
TREASURY_CHART_COLORS = {
    "UST_2Y_LEVEL": "#8E5A43",
    "UST_10Y_LEVEL": "#4E6C8C",
    "UST_30Y_LEVEL": "#4E7B52",
}
MACRO_CHART_COLORS = {
    "UST_2S10S": "#5F8D84",
    "UST_5S30S": "#5F8D84",
    "CPI_YOY": "#B08A3C",
    "BEI_5Y": "#B08A3C",
    "REAL_RATE_PROXY": "#8E7443",
    "FEDFUNDS_LEVEL": "#6A7FA0",
    "UNRATE_LEVEL": "#6C8E59",
    "IG_OAS_LEVEL": "#6F8FA7",
    "BBB_OAS_LEVEL": "#B07A4A",
    "HY_OAS_LEVEL": "#A55C45",
    "HY_MINUS_IG_OAS": "#B07A4A",
}
PERCENT_CHART_FEATURES = {
    "UST_2Y_LEVEL",
    "UST_10Y_LEVEL",
    "UST_30Y_LEVEL",
    "UST_2S10S",
    "UST_5S30S",
    "CPI_YOY",
    "BEI_5Y",
    "REAL_RATE_PROXY",
    "FEDFUNDS_LEVEL",
    "UNRATE_LEVEL",
}
SPARSE_BAR_FEATURES = {"CPI_YOY", "FEDFUNDS_LEVEL", "UNRATE_LEVEL"}


class MacroPage:
    """Render the macro page, including feature cards, charts, and regime summaries."""

    def __init__(self, macro_feature_store) -> None:
        self.macro_feature_store = macro_feature_store
        self.controls = DashboardControls()
        self.info_panel = InfoPanel()

    def _format_value(self, value: float | None) -> str:
        """Format a float to a 2dp comma-separated string, returning 'n/a' for missing values."""
        if value is None or pd.isna(value):
            return "n/a"
        return f"{value:,.2f}"

    def _format_delta(self, value: float | None) -> str:
        """Format a float as a signed 2dp string, returning 'n/a' for missing values."""
        if value is None or pd.isna(value):
            return "n/a"
        return f"{value:+.2f}"

    def _format_feature_value(
        self, feature_name: str, value: float | None, signed: bool = False
    ) -> str:
        """Format a feature value in its natural unit (bps for OAS, % for rates, plain otherwise)."""
        if feature_name in OAS_FEATURES:
            if value is None or pd.isna(value):
                return "n/a"
            number = value * 100.0
            return f"{number:+.0f} bps" if signed else f"{number:,.0f} bps"
        if feature_name in PERCENT_LEVEL_FEATURES:
            if value is None or pd.isna(value):
                return "n/a"
            return f"{value:+.2f}%" if signed else f"{value:,.2f}%"
        formatter = self._format_delta if signed else self._format_value
        return formatter(value)

    def _format_delta_value(self, feature_name: str, value: float | None) -> str:
        """Format a delta value with appropriate unit label (z-score prefix, bps, or signed float)."""
        if value is None or pd.isna(value):
            return "n/a"
        if feature_name in Z_SCORE_FEATURES:
            return f"z {value:+.2f}"
        if feature_name in OAS_FEATURES or feature_name in PERCENT_LEVEL_FEATURES:
            return f"{value * 100:+.0f} bps"
        return self._format_feature_value(feature_name, value, signed=True)

    def _badge_html(self, label: str, tone: str) -> str:
        """Return an HTML badge span colored by tone (positive / negative / neutral)."""
        color_map = {
            "positive": ("rgba(78, 123, 82, 0.10)", "#4E7B52"),
            "negative": ("rgba(165, 92, 69, 0.10)", "#A55C45"),
            "neutral": ("rgba(111, 123, 70, 0.10)", "#6F7B46"),
        }
        background, text = color_map.get(tone, color_map["neutral"])
        return (
            f"<div style='margin-top:0.36rem;'>"
            f"<span class='bb-regime-badge' style='border:1px solid {text};"
            f"background:{background};color:{text};'>"
            f"{label}</span></div>"
        )

    def _metric_tone(self, value: float | None) -> str:
        """Return 'positive', 'negative', or 'neutral' based on the sign of value."""
        if value is None or pd.isna(value):
            return "neutral"
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return "neutral"

    def _number(self, value: float | None, default: float = 0.0) -> float:
        """Return a safe float for rule logic and chart labels."""
        if value is None or pd.isna(value):
            return default
        return float(value)

    def _delta_html(self, label: str, text: str, value: float | None) -> str:
        """Return an HTML delta row with a directional arrow and tone-based CSS class."""
        tone = self._metric_tone(value)
        tone_class = {
            "positive": "bb-macro-card-delta--positive",
            "negative": "bb-macro-card-delta--negative",
            "neutral": "bb-macro-card-delta--neutral",
        }[tone]
        arrow = {"positive": "↑", "negative": "↓", "neutral": "→"}[tone]
        return f"<div class='bb-macro-card-delta {tone_class}'>{label}: {arrow} {text}</div>"

    def _latest_change(self, matrix: pd.DataFrame, feature_name: str) -> float | None:
        """Return the most recent day-over-day change for a feature, or None if insufficient data."""
        if feature_name not in matrix.columns:
            return None
        series = matrix[feature_name].dropna()
        if len(series) < 2:
            return None
        return float(series.iloc[-1] - series.iloc[-2])

    def _rule_based_regimes(self, matrix: pd.DataFrame) -> dict[str, tuple[str, str]]:
        """Derive duration, curve, inflation, and growth regime labels from current macro levels."""
        latest = {column: self._latest_value(matrix, column) for column in matrix.columns}
        ust_10y_change_20d = self._number(latest.get("UST_10Y_CHANGE_20D"))
        ust_2s10s = self._number(latest.get("UST_2S10S"))
        cpi_yoy = self._number(latest.get("CPI_YOY"))
        cpi_3m_ann = self._number(latest.get("CPI_3M_ANN"))
        bei_5y_change_20d = self._number(latest.get("BEI_5Y_CHANGE_20D"))
        unrate_3m_change = self._number(latest.get("UNRATE_3M_CHANGE"))

        duration = "Duration Bearish"
        duration_body = "10Y yields are rising over the last 20 trading days."
        if ust_10y_change_20d < -10:
            duration = "Duration Bullish"
            duration_body = "10Y yields have fallen materially over the last 20 trading days."
        elif abs(ust_10y_change_20d) <= 10:
            duration = "Duration Neutral"
            duration_body = "10Y yields are broadly range-bound versus the last 20 trading days."

        curve = "Curve Inverted"
        curve_body = "2s10s remains below zero."
        if ust_2s10s > 25:
            curve = "Curve Steepening"
            curve_body = "2s10s is decisively positive, signaling a steeper curve."
        elif ust_2s10s >= 0:
            curve = "Curve Flat"
            curve_body = "2s10s is positive but still compressed."

        inflation = "Inflation Cooling"
        inflation_body = "CPI YoY is below 2.5% and 3M annualized inflation is contained."
        if cpi_yoy > 3.0 or cpi_3m_ann > 3.0:
            inflation = "Inflation Hot"
            inflation_body = (
                "Headline inflation or its short-term annualized pace remains elevated."
            )
        elif bei_5y_change_20d > 0.25:
            inflation = "Inflation Repricing"
            inflation_body = "Breakevens have moved higher over the last 20 trading days."

        growth = "Growth Deteriorating"
        growth_body = "Unemployment has been rising over recent months."
        if unrate_3m_change < -0.1:
            growth = "Growth Improving"
            growth_body = "Unemployment has been falling over the last three months."
        elif abs(unrate_3m_change) <= 0.1:
            growth = "Growth Stable"
            growth_body = "Unemployment is broadly stable on a three-month view."

        return {
            "duration_regime": (duration, duration_body),
            "curve_regime": (curve, curve_body),
            "inflation_regime": (inflation, inflation_body),
            "growth_regime": (growth, growth_body),
        }

    def _latest_value(self, matrix: pd.DataFrame, feature_name: str) -> float | None:
        """Return the most recent non-null value for a feature column, or None if unavailable."""
        if feature_name not in matrix.columns:
            return None
        series = matrix[feature_name].dropna()
        if series.empty:
            return None
        return float(series.iloc[-1])

    def _latest_date(self, matrix: pd.DataFrame, feature_name: str):
        """Return the index timestamp of the most recent non-null observation for a feature, or None."""
        if feature_name not in matrix.columns:
            return None
        series = matrix[feature_name].dropna()
        if series.empty:
            return None
        return series.index[-1]

    def _display_series(self, feature_name: str, series: pd.Series) -> pd.Series:
        """Convert a raw feature series to display units (multiply OAS by 100 for basis points)."""
        return series * 100.0 if feature_name in OAS_FEATURES else series

    def _zscore(self, series: pd.Series, window: int) -> pd.Series:
        """Compute a rolling z-score over the given lookback window."""
        rolling_mean = series.rolling(window).mean()
        rolling_std = series.rolling(window).std(ddof=0)
        return (series - rolling_mean) / rolling_std.replace(0, np.nan)

    def _change(self, series: pd.Series, periods: int) -> pd.Series:
        """Return the absolute change in a series over the given number of periods."""
        return series - series.shift(periods)

    def _ensure_display_features(self, matrix: pd.DataFrame) -> pd.DataFrame:
        """Derive any display-only features (e.g. z-scores) not present in the stored matrix."""
        if matrix.empty:
            return matrix

        enriched = matrix.copy()

        if "UST_10Y_Z20" not in enriched.columns and "UST_10Y_LEVEL" in enriched.columns:
            enriched["UST_10Y_Z20"] = self._zscore(enriched["UST_10Y_LEVEL"], 20)

        return enriched

    def _feature_names(self) -> list[str]:
        """Build one stable feature list for cards, charts, and the yield curve."""
        feature_names = [item[1] for item in CARD_CONFIG]
        feature_names += [item[2] for item in CARD_CONFIG if item[2] is not None]
        for _, names in CHART_CONFIG:
            feature_names.extend(names)
        feature_names.extend(feature_name for _, _, feature_name in YIELD_CURVE_CONFIG)
        feature_names.extend(
            ["UST_2S10S_Z20", "UST_5S30S_Z20", "BEI_5Y_CHANGE_20D", "UNRATE_3M_CHANGE"]
        )
        return sorted(dict.fromkeys(feature_names))

    def _selected_lookback(self) -> int | None:
        """Render the window selector and return the corresponding lookback in trading days, or None for ALL."""
        selected_window = self.controls.render_select(
            "Macro Window",
            list(LOOKBACK_MAP),
            index=3,
            key="macro_window",
            label_visibility="collapsed",
            width=220,
        )
        return LOOKBACK_MAP.get(selected_window)

    def _render_header(self) -> int | None:
        """Render the page title and window control; return the selected lookback in trading days."""
        title_col, control_col = st.columns([1.55, 0.55], vertical_alignment="bottom")
        with title_col:
            st.markdown(
                """
                <div class="bb-macro-header">
                    <div class="bb-macro-page-title">Macro</div>
                    <div class="bb-macro-page-subtitle">
                        Rates, inflation, credit, and growth context for fixed-income ETF positioning.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with control_col:
            st.markdown(
                "<div class='bb-macro-control-label'>Macro Window</div>", unsafe_allow_html=True
            )
            lookback = self._selected_lookback()
        st.markdown("<div class='bb-macro-header-divider'></div>", unsafe_allow_html=True)
        return lookback

    def _matrix_start_date(self, lookback: int | None) -> str | None:
        """Convert a lookback in trading days to an ISO date string for the feature matrix query."""
        if lookback is None:
            return None
        return (
            (pd.Timestamp.utcnow().normalize() - pd.tseries.offsets.BDay(lookback + 10))
            .date()
            .isoformat()
        )

    def _windowed_matrix(self, matrix: pd.DataFrame, lookback: int | None) -> pd.DataFrame:
        """Slice the feature matrix to the most recent lookback rows, or return it unchanged for ALL."""
        if matrix.empty:
            return matrix
        return matrix.copy() if lookback is None else matrix.tail(min(lookback, len(matrix))).copy()

    def _curve_rows(self, matrix: pd.DataFrame) -> list[dict[str, object]]:
        """Build a list of tenor-keyed dicts for the yield curve chart from the current feature matrix."""
        rows: list[dict[str, object]] = []
        for tenor_label, maturity_years, feature_name in YIELD_CURVE_CONFIG:
            value = self._latest_value(matrix, feature_name)
            date = self._latest_date(matrix, feature_name)
            if value is None or pd.isna(value) or date is None:
                continue
            rows.append(
                {
                    "tenor": tenor_label,
                    "maturity_years": maturity_years,
                    "value": float(value),
                    "date": date,
                }
            )
        return rows

    def _chart_layout(
        self,
        title: str,
        *,
        height: int = 320,
        yaxis_title: str | None = None,
        margin: dict | None = None,
        xaxis: dict | None = None,
        legend: dict | None = None,
        font_size: int = 11,
    ) -> dict:
        """Return a Plotly layout dict using the dashboard's monospace font and responsive helpers."""
        return responsive_chart_layout(
            title,
            height=height,
            yaxis_title=yaxis_title,
            margin=margin,
            xaxis=xaxis,
            legend=legend,
            font_family='"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
            font_size=font_size,
        )

    def _render_chart_grid(self, matrix: pd.DataFrame, start_date, end_date) -> None:
        """Render all CHART_CONFIG entries as a two-row 5-column grid of Plotly charts."""
        st.markdown(
            """
            <div class="bb-macro-section-header">
                <div class="bb-macro-section-title">Macro Drivers</div>
                <div class="bb-macro-section-subtitle">
                    Cross-market trends shaping rate sensitivity, inflation expectations, credit tone, and growth context.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        chart_rows = [CHART_CONFIG[i : i + 5] for i in range(0, len(CHART_CONFIG), 5)]
        for row in chart_rows:
            columns = st.columns(len(row))
            for column, (title, feature_names) in zip(columns, row, strict=True):
                with column:
                    self._render_chart(matrix, title, feature_names, start_date, end_date)
            st.markdown("<div class='bb-metric-group-spacer'></div>", unsafe_allow_html=True)

    def _render_regimes(self, matrix: pd.DataFrame) -> None:
        """Render the four regime cards (duration, curve, inflation, growth) from rule-based signals."""
        st.markdown(
            """
            <div class="bb-macro-section-header">
                <div class="bb-macro-section-title">Macro Regime</div>
                <div class="bb-macro-section-subtitle">
                    Simple decision-layer signals for duration, curve shape, inflation tone, and growth stability.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        regimes = self._rule_based_regimes(matrix)
        cards = [
            ("Duration Regime", "duration_regime", "#B08A3C"),
            ("Curve Regime", "curve_regime", "#5F8D84"),
            ("Inflation Regime", "inflation_regime", "#A55C45"),
            ("Growth Regime", "growth_regime", "#4E7B52"),
        ]
        columns = st.columns(len(cards))
        for column, (title, key, accent) in zip(columns, cards, strict=True):
            with column:
                headline, body = regimes[key]
                st.markdown(
                    f"""
                    <div class="bb-macro-regime-card" style="border-left-color:{accent};">
                        <div class="bb-macro-regime-kicker" style="color:{accent};">{title}</div>
                        <div class="bb-macro-regime-headline">{headline}</div>
                        <div class="bb-macro-regime-body">{body}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        st.caption(
            "Rules are deliberately simple: duration uses 10Y changes, curve uses 2s10s level, inflation uses CPI and breakevens, and growth uses unemployment changes."
        )

    def _render_cards(self, matrix: pd.DataFrame) -> None:
        """Render the State of Macro card grid with latest values, deltas, and z-score badges."""
        cards: list[str] = []
        for label, feature_name, badge_feature, badge_label in CARD_CONFIG:
            value = self._latest_value(matrix, feature_name)
            delta_value = self._latest_change(matrix, feature_name)
            badge_value = self._latest_value(matrix, badge_feature) if badge_feature else None
            delta_text = self._format_delta_value(feature_name, delta_value)
            if badge_feature:
                footer_html = self._badge_html(
                    f"{badge_label} z {self._format_value(badge_value)}",
                    self._metric_tone(badge_value),
                )
            else:
                footer_html = ""

            cards.append(
                "<div class='bb-macro-card'>"
                f"<div class='bb-macro-card-label'>{label.upper()}</div>"
                f"<div class='bb-macro-card-value'>{self._format_feature_value(feature_name, value)}</div>"
                f"{self._delta_html('Latest change', delta_text, delta_value)}"
                f"{footer_html}"
                "</div>"
            )

        st.markdown(
            f"""
            <div class='bb-macro-snapshot-panel' style='min-height:100%;height:100%;display:flex;flex-direction:column;'>
                <div class='bb-macro-snapshot-header' style='padding-top:1.18rem;'>
                    <div class='bb-macro-snapshot-title'>State of Macro</div>
                    <div class='bb-macro-snapshot-subtitle'>Key levels, latest moves, and context chips for the current window.</div>
                </div>
                <div class='bb-macro-snapshot-body' style='flex:1;display:flex;align-items:center;padding-top:7rem;'>
                    <div class='bb-macro-card-grid bb-macro-card-grid--compact' style='width:100%;margin:0;'>{''.join(cards)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    def _nelson_siegel_curve(
        self, maturities: np.ndarray, beta0: float, beta1: float, beta2: float, tau: float
    ) -> np.ndarray:
        """Evaluate the Nelson-Siegel yield curve model at the given maturities."""
        safe_tau = max(float(tau), 1e-6)
        load1 = (1.0 - np.exp(-maturities / safe_tau)) / (maturities / safe_tau)
        load2 = load1 - np.exp(-maturities / safe_tau)
        return beta0 + beta1 * load1 + beta2 * load2

    def _fit_nelson_siegel(self, maturities: np.ndarray, yields: np.ndarray) -> np.ndarray | None:
        """Fit Nelson-Siegel parameters via L-BFGS-B; return the parameter array or None on failure."""
        if len(maturities) < 4:
            return None

        initial_guess = np.array([yields[-1], yields[0] - yields[-1], 0.0, 1.5], dtype=float)

        def objective(params: np.ndarray) -> float:
            fitted = self._nelson_siegel_curve(maturities, *params)
            residuals = yields - fitted
            return float(np.sum(residuals**2))

        result = minimize(
            objective,
            initial_guess,
            method="L-BFGS-B",
            bounds=[(0.0, 10.0), (-10.0, 10.0), (-10.0, 10.0), (0.05, 20.0)],
        )
        if not result.success:
            return None
        return result.x

    def _render_yield_curve(self, matrix: pd.DataFrame) -> None:
        """Render the yield curve chart with observed points and a Nelson-Siegel smooth overlay."""
        curve_rows = self._curve_rows(matrix)
        if not curve_rows:
            st.info("No yield-curve levels available yet.")
            return

        curve_df = pd.DataFrame(curve_rows).sort_values("maturity_years").reset_index(drop=True)
        maturities = curve_df["maturity_years"].to_numpy(dtype=float)
        yields = curve_df["value"].to_numpy(dtype=float)
        tenor_positions = np.arange(len(curve_df), dtype=float)
        fitted_params = self._fit_nelson_siegel(maturities, yields)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=tenor_positions,
                y=curve_df["value"],
                mode="markers",
                name="Observed",
                line=dict(color="#6F7B46", width=0),
                marker=dict(size=8, color="#5F8D84"),
                hovertemplate="%{text}<br>%{y:.2f}%<extra></extra>",
                text=curve_df["tenor"],
            )
        )
        fig.add_trace(
            go.Scatter(
                x=tenor_positions,
                y=curve_df["value"],
                mode="lines",
                name="Observed segments",
                line=dict(color="#5F8D84", width=1, dash="dot"),
                hoverinfo="skip",
            )
        )
        if fitted_params is not None:
            smooth_positions = np.linspace(tenor_positions.min(), tenor_positions.max(), 200)
            smooth_maturities = np.interp(smooth_positions, tenor_positions, maturities)
            smooth_curve = self._nelson_siegel_curve(smooth_maturities, *fitted_params)
            fig.add_trace(
                go.Scatter(
                    x=smooth_positions,
                    y=smooth_curve,
                    mode="lines",
                    name="Nelson-Siegel fit",
                    line=dict(color="#1F271C", width=3),
                    customdata=smooth_maturities,
                    hovertemplate="%{customdata:.2f}Y<br>%{y:.2f}%<extra></extra>",
                )
            )
        fig.update_layout(
            **self._chart_layout(
                "Yield Curve",
                height=540,
                yaxis_title="Yield (%)",
                margin=dict(l=48, r=48, t=96, b=60),
                xaxis=dict(
                    title="Tenor",
                    showgrid=True,
                    gridcolor="#D8D4C7",
                    automargin=True,
                    title_standoff=16,
                    tickmode="array",
                    tickvals=tenor_positions.tolist(),
                    ticktext=curve_df["tenor"].tolist(),
                ),
            ),
        )
        curve_dates: list[pd.Timestamp] = []
        for row in curve_rows:
            date = row["date"]
            if isinstance(date, pd.Timestamp):
                curve_dates.append(date)
        curve_date = max(curve_dates) if curve_dates else None
        st.markdown(
            """
            <div class="bb-macro-featured-header">
                <div class="bb-macro-featured-kicker">Featured View</div>
                <div class="bb-macro-featured-title">Yield Curve</div>
                <div class="bb-macro-featured-subtitle">
                    Treasury term structure across the curve, with observed points and a smooth fitted overlay.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)
        if curve_date is not None:
            caption = f"Latest available yield-curve snapshot as of {pd.Timestamp(curve_date).strftime('%Y-%m-%d')}."
            if fitted_params is not None:
                caption += " Curve overlay uses a smooth Nelson-Siegel fit rather than linear interpolation."
            st.markdown(
                f"<div class='bb-macro-featured-caption'>{caption}</div>", unsafe_allow_html=True
            )

    def _render_chart(
        self, matrix: pd.DataFrame, title: str, feature_names: list[str], start_date, end_date
    ) -> None:
        """Render one macro chart panel as a line chart (or sparse bar for CPI/FEDFUNDS/UNRATE)."""
        filtered = matrix.loc[
            (matrix.index >= start_date) & (matrix.index <= end_date), feature_names
        ].copy()
        if filtered.empty:
            st.info(f"No data available for {title.lower()} in the selected window.")
            return

        fig = go.Figure()
        traces_added = 0
        use_sparse_bar = len(feature_names) == 1 and feature_names[0] in SPARSE_BAR_FEATURES
        for idx, feature_name in enumerate(feature_names):
            if feature_name not in filtered.columns:
                continue
            series = filtered[feature_name].dropna()
            if series.empty:
                continue
            line_color = TREASURY_CHART_COLORS.get(feature_name) or MACRO_CHART_COLORS.get(
                feature_name
            )
            if line_color is None:
                line_color = CHART_PALETTE[idx % len(CHART_PALETTE)]
            display_series = self._display_series(feature_name, series)
            if use_sparse_bar:
                fig.add_trace(
                    go.Bar(
                        x=series.index,
                        y=display_series,
                        name=FEATURE_LABELS.get(feature_name, feature_name.replace("_", " ")),
                        marker=dict(color=line_color, line=dict(color=line_color, width=0)),
                        opacity=0.82,
                        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>",
                    )
                )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=series.index,
                        y=display_series,
                        mode="lines",
                        name=FEATURE_LABELS.get(feature_name, feature_name.replace("_", " ")),
                        line=dict(color=line_color, width=2),
                        connectgaps=False,
                        hovertemplate=(
                            "%{x|%Y-%m-%d}<br>%{y:.0f} bps<extra></extra>"
                            if feature_name in OAS_FEATURES
                            else None
                        ),
                    )
                )
            traces_added += 1

        if traces_added == 0:
            st.info(f"No data available for {title.lower()} in the selected window.")
            return

        yaxis_title = None
        if any(name in OAS_FEATURES for name in feature_names):
            yaxis_title = "bps"
        elif any(name in PERCENT_CHART_FEATURES for name in feature_names):
            yaxis_title = "%"

        fig.update_layout(
            **self._chart_layout(
                title,
                yaxis_title=yaxis_title,
                margin=dict(l=24, r=24, t=110, b=42),
                font_size=10,
            )
        )
        if use_sparse_bar:
            fig.update_layout(bargap=0.78)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)

    def render(self) -> None:
        """Render the full macro page: header, yield curve, State of Macro cards, chart grid, and regimes."""
        feature_names = self._feature_names()
        lookback = self._render_header()
        start_date_filter = self._matrix_start_date(lookback)

        with timed_block("macro.load_feature_matrix"):
            matrix = cached_feature_matrix(
                app_cache_key(self.macro_feature_store.engine),
                tuple(feature_names),
                start_date_filter,
                None,
                self.macro_feature_store,
            )
        if matrix.empty:
            st.warning("No macro features found. Run scripts.macro.build_macro_features first.")
            return
        filtered_matrix = self._ensure_display_features(self._windowed_matrix(matrix, lookback))

        if filtered_matrix.empty:
            st.warning("No macro features available for the selected window.")
            return

        start_date = filtered_matrix.index.min()
        end_date = filtered_matrix.index.max()

        top_left, top_right = st.columns([1.58, 1.42], vertical_alignment="top")
        with top_left:
            st.markdown(
                "<div class='bb-macro-panel-marker bb-macro-panel-marker--featured'></div>",
                unsafe_allow_html=True,
            )
            with timed_block("macro.render_yield_curve"):
                self._render_yield_curve(filtered_matrix)
        with top_right:
            st.markdown(
                "<div class='bb-macro-panel-marker bb-macro-panel-marker--summary'></div>",
                unsafe_allow_html=True,
            )
            with timed_block("macro.render_cards"):
                self._render_cards(filtered_matrix)
        self._render_chart_grid(filtered_matrix, start_date, end_date)
        self._render_regimes(filtered_matrix)
