"""Plotly chart configuration and responsive layout helpers for the dashboard."""

from __future__ import annotations

PLOTLY_CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
}


_GRID_COLOR = "rgba(200,195,185,0.45)"
_AXIS_LINE_COLOR = "rgba(200,195,185,0.70)"
_CHART_BG = "#FFFFFF"


def _responsive_legend(height: int) -> dict:
    """Return Plotly legend kwargs sized appropriately for the given chart height."""
    if height >= 460:
        font_size = 10
        y_pos = 1.08
        item_width = 42
    elif height >= 380:
        font_size = 9
        y_pos = 1.10
        item_width = 38
    else:
        font_size = 7
        y_pos = 1.30
        item_width = 30

    return dict(
        orientation="h",
        yanchor="top",
        y=y_pos,
        xanchor="center",
        x=0.5,
        font=dict(size=font_size),
        bgcolor="rgba(0,0,0,0)",
        itemwidth=item_width,
        tracegroupgap=6,
    )


def responsive_chart_layout(
    title: str,
    *,
    height: int,
    yaxis_title: str | None = None,
    margin: dict | None = None,
    xaxis: dict | None = None,
    legend: dict | None = None,
    font_family: str,
    font_size: int = 11,
) -> dict:
    """Return a Plotly layout dict with consistent terminal styling and responsive legend."""
    return dict(
        title=dict(
            text=title,
            x=0.01,
            xanchor="left",
            y=0.99,
            pad=dict(t=6, b=6),
            font=dict(size=10, color="#8D8779"),
        ),
        template="plotly_white",
        paper_bgcolor=_CHART_BG,
        plot_bgcolor=_CHART_BG,
        margin=margin or dict(l=24, r=16, t=72, b=40),
        height=height,
        font=dict(color="#1F271C", family=font_family, size=font_size),
        xaxis=xaxis
        or dict(
            showgrid=True,
            gridcolor=_GRID_COLOR,
            gridwidth=1,
            linecolor=_AXIS_LINE_COLOR,
            zerolinecolor=_GRID_COLOR,
            automargin=True,
            title_standoff=12,
            title_font=dict(size=max(font_size - 1, 9), color="#8D8779"),
            tickfont=dict(size=max(font_size - 1, 8), color="#6B6560"),
        ),
        yaxis=dict(
            title=yaxis_title,
            showgrid=True,
            gridcolor=_GRID_COLOR,
            gridwidth=1,
            linecolor=_AXIS_LINE_COLOR,
            zerolinecolor=_GRID_COLOR,
            automargin=True,
            title_standoff=10,
            title_font=dict(size=max(font_size - 1, 9), color="#8D8779"),
            tickfont=dict(size=max(font_size - 1, 8), color="#6B6560"),
        ),
        legend=legend or _responsive_legend(height),
    )
