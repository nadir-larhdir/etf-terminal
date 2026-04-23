from __future__ import annotations


def responsive_chart_layout(
    title: str,
    *,
    height: int,
    yaxis_title: str | None = None,
    margin: dict | None = None,
    xaxis: dict | None = None,
    legend: dict | None = None,
    font_family: str,
) -> dict:
    return dict(
        title=dict(text=title, x=0.02, xanchor="left", y=0.97, pad=dict(t=10, b=10)),
        template="plotly_white",
        paper_bgcolor="#FBF8F1",
        plot_bgcolor="#FBF8F1",
        margin=margin or dict(l=24, r=24, t=82, b=48),
        height=height,
        font=dict(color="#1F271C", family=font_family, size=12),
        xaxis=xaxis
        or dict(
            showgrid=True,
            gridcolor="#D8D4C7",
            linecolor="#C9C4B4",
            zerolinecolor="#D8D4C7",
            automargin=True,
            title_standoff=14,
        ),
        yaxis=dict(
            title=yaxis_title,
            showgrid=True,
            gridcolor="#D8D4C7",
            linecolor="#C9C4B4",
            zerolinecolor="#D8D4C7",
            automargin=True,
            title_standoff=10,
        ),
        legend=legend
        or dict(
            orientation="h",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=0.0,
            font=dict(size=9),
            bgcolor="rgba(0,0,0,0)",
            itemwidth=40,
        ),
    )
