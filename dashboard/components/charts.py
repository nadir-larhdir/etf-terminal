"""Plotly chart rendering functions for price, volume, and RV analysis panels."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pandas import DatetimeIndex

from dashboard.components.controls import WINDOW_LOOKBACK_MAP
from dashboard.mobile import PLOTLY_CHART_CONFIG, responsive_chart_layout

TERMINAL_FONT = (
    '"SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
)
CHART_GRID = "rgba(200,195,185,0.45)"
CHART_INK = "#1F271C"
CHART_MUTED = "#9A9288"
CHART_OLIVE = "#8AA05A"
CHART_OLIVE_SOFT = "rgba(138, 160, 90, 0.10)"
CHART_TEAL = "#7FB9AA"
CHART_UP = "#5DA861"
CHART_DOWN = "#C46A5A"
CHART_GOLD = "#C4952A"


def _filter_by_period(hist: pd.DataFrame, period_label: str) -> pd.DataFrame:
    """Return the trailing N rows of hist corresponding to the given period label."""
    lookback = WINDOW_LOOKBACK_MAP.get(period_label, len(hist))
    return hist.tail(min(lookback, len(hist))).copy()


def _filter_by_dates(hist: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """Slice hist to [start_date, end_date]; falls back to the last row if empty."""
    idx = DatetimeIndex(hist.index)
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    filtered = hist.loc[(idx >= start_ts) & (idx <= end_ts)].copy()
    return filtered if not filtered.empty else hist.tail(1).copy()


def compute_default_date_range(hist: pd.DataFrame, period_label: str):
    """Return the (min_date, max_date) pair for the trailing window matching period_label."""
    filtered = _filter_by_period(hist, period_label)
    idx = DatetimeIndex(filtered.index)
    return idx.min().date(), idx.max().date()


def format_volume_label(value: float) -> str:
    """Format a raw volume integer as a compact string (e.g. '24M', '1MM')."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:.0f}MM"
    if value >= 1_000:
        return f"{value / 1_000:.0f}M"
    return f"{value:.0f}"


def _apply_terminal_chart_layout(
    fig: go.Figure, *, title: str, height: int, margin=None, legend=None
) -> None:
    """Apply the shared terminal chart layout to fig in-place."""
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
    """Render a price-action chart with mean ± 1σ bands and colour-coded above/below lines."""
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
            line=dict(color=CHART_MUTED, width=1.0),
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
            line=dict(color=CHART_GOLD, width=0.9, dash="dot"),
            hovertemplate="+1σ: %{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=[lower_band] * len(filtered),
            mode="lines",
            name="-1σ",
            line=dict(color=CHART_GOLD, width=0.9, dash="dot"),
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
            line=dict(color=CHART_UP, width=2.0),
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
            line=dict(color=CHART_DOWN, width=2.0),
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
            line=dict(color=CHART_OLIVE, width=1.2),
            hovertemplate="MEAN: %{y:,.2f}<extra></extra>",
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=f"Price Action ({ticker})",
        height=460,
        margin=dict(l=16, r=16, t=60, b=24),
    )
    fig.update_layout(
        xaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            range=[filtered.index.min(), filtered.index.max()],
            rangeslider=dict(visible=False),
            fixedrange=True,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            range=[price_min - padding, price_max + padding],
            tickformat=".2f",
            fixedrange=True,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_volume_chart(hist: pd.DataFrame, ticker: str, start_date, end_date):
    """Render a bar-chart of trading volume with a 30-day average overlay."""
    filtered = _filter_by_dates(hist, start_date, end_date)

    volume_series = filtered["volume"]
    mean_volume = float(volume_series.mean())
    bar_colors = [
        "rgba(93,168,97,0.75)" if value >= mean_volume else "rgba(196,106,90,0.65)"
        for value in volume_series
    ]

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
            marker_line_width=0,
            hovertemplate="%{x|%b %d, %Y}<br>VOLUME: %{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=filtered.index,
            y=[mean_volume] * len(filtered),
            mode="lines",
            name="30D Avg",
            line=dict(color=CHART_OLIVE, width=1.4),
            hovertemplate="30D AVG: %{y:,.0f}<extra></extra>",
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=f"Trading Activity ({ticker})",
        height=460,
        margin=dict(l=16, r=16, t=60, b=24),
    )
    fig.update_layout(
        bargap=0.20,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            range=[filtered.index.min(), filtered.index.max()],
            rangeslider=dict(visible=False),
            fixedrange=True,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_text,
            range=[0, max_volume * 1.15],
            fixedrange=True,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_zscore_chart(
    z_series: pd.Series, ticker_a: str, ticker_b: str, *, title: str | None = None
):
    """Render the RV z-score series with ±1σ/±2σ reference lines and extreme-point markers."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=z_series.index,
            y=z_series,
            mode="lines",
            name="Z-Score",
            line=dict(color="#6F6A63", width=1.9),
        )
    )

    for level, label in [
        (3, "+3 Std"),
        (2, "+2 Std"),
        (1, "+1 Std"),
        (0, "Mean"),
        (-1, "-1 Std"),
        (-2, "-2 Std"),
        (-3, "-3 Std"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=z_series.index,
                y=[level] * len(z_series),
                mode="lines",
                name=label,
                line=dict(
                    color=(
                        "#A9A39B"
                        if level == 0
                        else "#D9C49B" if abs(level) == 1 else "#E0B1A6" if level > 1 else "#BCD5C7"
                    ),
                    width=1.0 if level == 0 else 0.8,
                    dash="dot" if level != 0 else "solid",
                ),
                hoverinfo="skip",
            )
        )

    extreme_mask = z_series.abs() >= 2
    fig.add_trace(
        go.Scatter(
            x=z_series.index[extreme_mask],
            y=z_series[extreme_mask],
            mode="markers",
            name="Extreme",
            marker=dict(color=CHART_DOWN, size=5, symbol="circle"),
            showlegend=False,
        )
    )

    last_value = float(z_series.iloc[-1])
    fig.add_annotation(
        x=z_series.index[-1],
        y=last_value,
        xanchor="left",
        yanchor="middle",
        xshift=18,
        text=f"{last_value:.2f}",
        showarrow=False,
        bgcolor="#7A766F",
        bordercolor="#7A766F",
        font=dict(color="#FBF8F1", size=10, family=TERMINAL_FONT),
        borderpad=4,
    )

    _apply_terminal_chart_layout(
        fig,
        title=title or f"Z-Score ({ticker_a} / {ticker_b})",
        height=380,
        margin=dict(l=16, r=44, t=24, b=24),
    )
    fig.update_layout(
        paper_bgcolor="#FBF8F1",
        plot_bgcolor="#FBF8F1",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0.5,
            xanchor="center",
            font=dict(size=9, color="#6B6560"),
        ),
        xaxis=dict(
            showgrid=False,
            gridcolor=CHART_GRID,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
            range=[-3.4, 3.4],
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_return_spread_chart(
    ratio_series: pd.Series, ticker_a: str, ticker_b: str, *, title: str | None = None
):
    """Render the cumulative beta-adjusted return spread between two ETFs."""
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=ratio_series.index,
            y=ratio_series,
            mode="lines",
            name="Spread",
            line=dict(color=CHART_TEAL, width=1.8),
            fill="tozeroy",
            fillcolor="rgba(127,185,170,0.08)",
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=title or f"Spread ({ticker_a} / {ticker_b})",
        height=380,
        margin=dict(l=16, r=16, t=24, b=24),
    )
    fig.update_layout(
        paper_bgcolor="#FBF8F1",
        plot_bgcolor="#FBF8F1",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0.5,
            xanchor="center",
            font=dict(size=9, color="#6B6560"),
        ),
        xaxis=dict(
            showgrid=False,
            gridcolor=CHART_GRID,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)


def render_beta_adjusted_z_chart(
    z_series: pd.Series,
    beta_series: pd.Series,
    ticker_a: str,
    ticker_b: str,
    *,
    title: str | None = None,
):
    """Render the rolling-beta-adjusted z-score series for the given pair."""
    adj_z = z_series * beta_series

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=adj_z.index,
            y=adj_z,
            mode="lines",
            name="Beta-Adj Z",
            line=dict(color="#7B6BA8", width=1.8),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=adj_z.index,
            y=[0] * len(adj_z),
            mode="lines",
            name="Mean",
            line=dict(color=CHART_OLIVE, width=1.0),
        )
    )

    _apply_terminal_chart_layout(
        fig,
        title=title or f"Beta-Adj Z ({ticker_a} / {ticker_b})",
        height=380,
        margin=dict(l=16, r=16, t=24, b=24),
    )
    fig.update_layout(
        paper_bgcolor="#FBF8F1",
        plot_bgcolor="#FBF8F1",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            x=0.5,
            xanchor="center",
            font=dict(size=9, color="#6B6560"),
        ),
        xaxis=dict(
            showgrid=False,
            gridcolor=CHART_GRID,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            automargin=True,
            tickfont=dict(size=10, color="#6B6560"),
        ),
    )

    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CHART_CONFIG)
