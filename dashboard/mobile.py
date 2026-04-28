"""Plotly chart configuration and responsive layout helpers for the dashboard."""

from __future__ import annotations

PLOTLY_CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "responsive": True,
}


def _responsive_legend(height: int) -> dict:
    """Return Plotly legend kwargs sized appropriately for the given chart height."""
    if height >= 520:
        font_size = 10
        y_pos = 1.12
        item_width = 42
    elif height >= 420:
        font_size = 9
        y_pos = 1.11
        item_width = 38
    else:
        font_size = 7
        y_pos = 1.35
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
        tracegroupgap=8,
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
        title=dict(text=title, x=0.02, xanchor="left", y=0.985, pad=dict(t=8, b=10)),
        template="plotly_white",
        paper_bgcolor="#FBF8F1",
        plot_bgcolor="#FBF8F1",
        margin=margin or dict(l=24, r=24, t=118, b=48),
        height=height,
        font=dict(color="#1F271C", family=font_family, size=font_size),
        xaxis=xaxis
        or dict(
            showgrid=True,
            gridcolor="#D8D4C7",
            linecolor="#C9C4B4",
            zerolinecolor="#D8D4C7",
            automargin=True,
            title_standoff=14,
            title_font=dict(size=max(font_size - 1, 9)),
            tickfont=dict(size=max(font_size - 1, 8)),
        ),
        yaxis=dict(
            title=yaxis_title,
            showgrid=True,
            gridcolor="#D8D4C7",
            linecolor="#C9C4B4",
            zerolinecolor="#D8D4C7",
            automargin=True,
            title_standoff=10,
            title_font=dict(size=max(font_size - 1, 9)),
            tickfont=dict(size=max(font_size - 1, 8)),
        ),
        legend=legend or _responsive_legend(height),
    )
