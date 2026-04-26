import pandas as pd
from pandas import DatetimeIndex
import plotly.graph_objects as go
import streamlit as st

from dashboard.components.controls import WINDOW_LOOKBACK_MAP
from dashboard.mobile import PLOTLY_CHART_CONFIG, responsive_chart_layout

TERMINAL_FONT = (
    '"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
)
CHART_GRID = "#D8D4C7"
CHART_INK = "#1F271C"
CHART_MUTED = "#7A7568"
CHART_OLIVE = "#6F7B46"
CHART_OLIVE_SOFT = "rgba(111, 123, 70, 0.10)"
CHART_TEAL = "#5F8D84"
CHART_UP = "#4E7B52"
CHART_DOWN = "#A55C45"
CHART_GOLD = "#C9A64B"


def _filter_by_period(hist: pd.DataFrame, period_label: str) -> pd.DataFrame:
    lookback = WINDOW_LOOKBACK_MAP.get(period_label, len(hist))
    return hist.tail(min(lookback, len(hist))).copy()


def _filter_by_dates(hist: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    idx = DatetimeIndex(hist.index)
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    filtered = hist.loc[(idx >= start_ts) & (idx <= end_ts)].copy()
    return filtered if not filtered.empty else hist.tail(1).copy()


def compute_default_date_range(hist: pd.DataFrame, period_label: str):
    filtered = _filter_by_period(hist, period_label)
    idx = DatetimeIndex(filtered.index)
    return idx.min().date(), idx.max().date()


def format_volume_label(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.0f}MM"
    if value >= 1_000:
        return f"{value / 1_000:.0f}M"
    return f"{value:.0f}"


def _apply_terminal_chart_layout(
    fig: go.Figure, *, title: str, height: int, margin=None, legend=None
) -> None:
    fig.update_layout(
        **responsive_chart_layout(
            title,
            height=height,
            margin=margin,
            legend=legend,
            font_family=TERMINAL_FONT,
        )
    )


def render_price_chart(hist: pd.DataFrame, ticker: str, start_date, end_date):
    filtered = _filter_by_dates(hist, start_date, end_date)

    close_series = filtered["close"]
    mean_price = float(close_series.mean())
    std_price = float(close_series.std(ddof=0)) if len(close_series) > 1 else 0.0
    upper_band = mean_price + std_price
    lower_band = mean_price - std_price

    above_mean = close_series.where(close_series >= mean_price)
    below_mean = close_series.where(close_series < mean_price)

    price_min = min(float(close_series.min()), lower_band)
    price_max = max(float(close_series.max()), upper_band)
    padding = max((price_max - price_min) * 0.12, 0.25)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=close_series,
            mode="lines",
            name="Price",
            line=dict(color=CHART_MUTED, width=1.2),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=[upper_band] * len(filtered),
            mode="lines",
            name="+1σ",
            line=dict(color=CHART_GOLD, width=1, dash="dot"),
            hovertemplate="+1σ: %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=[lower_band] * len(filtered),
            mode="lines",
            name="-1σ",
            line=dict(color=CHART_GOLD, width=1, dash="dot"),
            fill="tonexty",
            fillcolor=CHART_OLIVE_SOFT,
            hovertemplate="-1σ: %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=above_mean,
            mode="lines",
            name="Above Mean",
            line=dict(color=CHART_UP, width=2.5),
            hovertemplate="%{x|%b %d, %Y}<br>PX_LAST: %{y:,.2f}<extra></extra>",
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=below_mean,
            mode="lines",
            name="Below Mean",
            line=dict(color=CHART_DOWN, width=2.5),
            hovertemplate="%{x|%b %d, %Y}<br>PX_LAST: %{y:,.2f}<extra></extra>",
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=[mean_price] * len(filtered),
            mode="lines",
            name="Mean",
            line=dict(color=CHART_OLIVE, width=1.5),
            hovertemplate="MEAN: %{y:,.2f}<extra></extra>",
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=f"{ticker} Price Action",
        height=520,
        margin=dict(l=20, r=20, t=50, b=30),
    )
    fig.update_layout(
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            range=[filtered.index.min(), filtered.index.max()],
            rangeslider=dict(visible=False),
            fixedrange=True,
            automargin=True,
        ),
        yaxis=dict(
            title="Price",
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            range=[price_min - padding, price_max + padding],
            tickformat=".2f",
            fixedrange=True,
            automargin=True,
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_volume_chart(hist: pd.DataFrame, ticker: str, start_date, end_date):
    filtered = _filter_by_dates(hist, start_date, end_date)

    volume_series = filtered["volume"]
    mean_volume = float(volume_series.mean())
    bar_colors = [CHART_UP if value >= mean_volume else CHART_DOWN for value in volume_series]

    max_volume = float(volume_series.max())
    step = (
        5_000_000
        if max_volume <= 50_000_000
        else 10_000_000 if max_volume <= 100_000_000 else 20_000_000
    )
    tick_vals = list(range(0, int(max_volume * 1.15) + step, step))
    tick_text = [format_volume_label(v) for v in tick_vals]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=filtered.index,
            y=volume_series,
            name="Volume",
            marker_color=bar_colors,
            hovertemplate="%{x|%b %d, %Y}<br>VOLUME: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=[mean_volume] * len(filtered),
            mode="lines",
            name="Mean",
            line=dict(color=CHART_OLIVE, width=1.5),
            hovertemplate="MEAN: %{y:,.0f}<extra></extra>",
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=f"{ticker} Trading Activity",
        height=520,
        margin=dict(l=20, r=20, t=50, b=30),
    )
    fig.update_layout(
        bargap=0.15,
        xaxis=dict(
            title="Date",
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            range=[filtered.index.min(), filtered.index.max()],
            rangeslider=dict(visible=False),
            fixedrange=True,
            automargin=True,
        ),
        yaxis=dict(
            title="Volume",
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[0, max_volume * 1.15],
            fixedrange=True,
            automargin=True,
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_zscore_chart(z_series: pd.Series, ticker_a: str, ticker_b: str):
    fig = go.Figure()

    # Main Z line
    fig.add_trace(
        go.Scatter(
            x=z_series.index,
            y=z_series,
            mode="lines",
            name="Z-Score",
            line=dict(color=CHART_MUTED, width=1.5),
        )
    )

    # Sigma lines
    for level, label in [(2, "+2σ"), (1, "+1σ"), (0, "Mean"), (-1, "-1σ"), (-2, "-2σ")]:
        fig.add_trace(
            go.Scatter(
                x=z_series.index,
                y=[level] * len(z_series),
                mode="lines",
                name=label,
                line=dict(
                    color=CHART_OLIVE if level == 0 else CHART_GOLD,
                    width=1,
                    dash="dot" if level != 0 else "solid",
                ),
                hoverinfo="skip",
            )
        )

    # Highlight extreme points
    extreme_mask = z_series.abs() >= 2
    fig.add_trace(
        go.Scatter(
            x=z_series.index[extreme_mask],
            y=z_series[extreme_mask],
            mode="markers",
            name="Extreme",
            marker=dict(color=CHART_DOWN, size=6),
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=f"RV Z-Score: {ticker_a}/{ticker_b}",
        height=420,
    )
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor=CHART_GRID, automargin=True),
        yaxis=dict(showgrid=True, gridcolor=CHART_GRID, automargin=True),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_return_spread_chart(ratio_series: pd.Series, ticker_a: str, ticker_b: str):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=ratio_series.index,
            y=ratio_series,
            mode="lines",
            name="Ratio",
            line=dict(color=CHART_TEAL, width=1.5),
        )
    )

    _apply_terminal_chart_layout(fig, title=f"Return Spread: {ticker_a}/{ticker_b}", height=420)
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor=CHART_GRID, automargin=True),
        yaxis=dict(showgrid=True, gridcolor=CHART_GRID, automargin=True),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_beta_adjusted_z_chart(
    z_series: pd.Series, beta_series: pd.Series, ticker_a: str, ticker_b: str
):
    adj_z = z_series * beta_series

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=adj_z.index,
            y=adj_z,
            mode="lines",
            name="Beta-Adj Z",
            line=dict(color=CHART_TEAL, width=1.5),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=adj_z.index,
            y=[0] * len(adj_z),
            mode="lines",
            name="Mean",
            line=dict(color=CHART_OLIVE, width=1),
        )
    )

    _apply_terminal_chart_layout(fig, title=f"Beta-Adjusted Z: {ticker_a}/{ticker_b}", height=420)
    fig.update_layout(
        xaxis=dict(showgrid=True, gridcolor=CHART_GRID, automargin=True),
        yaxis=dict(showgrid=True, gridcolor=CHART_GRID, automargin=True),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)
