from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from dashboard.render import ENVIRONMENT, TEMPLATE_DIR, render, stylesheet


def test_every_shipped_template_parses() -> None:
    names = ENVIRONMENT.list_templates(extensions=("html", "svg"))

    assert names, "no templates were discovered"
    for name in names:
        ENVIRONMENT.get_template(name)  # raises TemplateSyntaxError on a malformed template


def test_templates_live_in_the_dashboard_package() -> None:
    assert TEMPLATE_DIR.is_dir()


def test_interpolated_values_are_html_escaped() -> None:
    html = render("home/regime_card.html", card=_card(label="<script>alert(1)</script>"))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_a_rendered_fragment_composes_into_another_template_unescaped() -> None:
    """A footer is itself a rendered template; composing it must not escape it a second time."""
    from dashboard.presenters.analytics import DurationScale, MetricCard

    footer = render("analytics/duration_scale.html", scale=DurationScale.from_years(5.7))
    html = render(
        "analytics/metric_card.html", card=MetricCard("Est. Duration", "5.7y"), footer=footer
    )

    assert 'class="an-scale"' in html
    assert "&lt;div" not in html


def test_composing_fragments_still_escapes_the_data_inside_them() -> None:
    from dashboard.presenters.analytics import MetricCard

    html = render(
        "analytics/metric_card.html",
        card=MetricCard("Label", "<img src=x onerror=alert(1)>"),
        footer=None,
    )

    assert "<img" not in html
    assert "&lt;img" in html


def test_a_missing_template_variable_fails_loudly() -> None:
    with pytest.raises(UndefinedError):
        render("home/regime_card.html")


def test_rendered_output_is_a_single_line_so_streamlit_does_not_treat_it_as_code() -> None:
    html = render("home/market_strip.html", tiles=[], latest_date="2026-08-21")

    assert "\n" not in html
    assert not html.startswith(" ")


def test_market_strip_renders_one_cell_per_tile() -> None:
    from dashboard.presenters import SnapshotTile

    tiles = [
        SnapshotTile.from_move("UST_10Y_LEVEL", "US 10Y", "UST", 4.37, 0.02),
        SnapshotTile.from_move("HY_OAS_LEVEL", "HY OAS", "Spread", 3.20, -0.05),
    ]

    html = render("home/market_strip.html", tiles=tiles, latest_date="2026-08-21")

    assert html.count("home-strip-cell") == 2
    assert "US 10Y" in html and "HY OAS" in html
    assert "2026-08-21" in html


def test_regime_card_places_the_marker_at_the_given_position() -> None:
    html = render("home/regime_card.html", card=_card(position=73.5))

    assert "left:calc(73.5% - 6px)" in html


@pytest.mark.parametrize(
    ("net", "marker"), [(3, "▲"), (-3, "▼"), (0, "—")], ids=["up", "down", "flat"]
)
def test_direction_badge_shows_the_right_marker(net: int, marker: str) -> None:
    html = render("home/direction_badge.html", net=net, label="Broad")

    assert marker in html


def test_direction_badge_shows_a_positive_count_for_a_negative_net() -> None:
    html = render("home/direction_badge.html", net=-4, label="Weakening")

    assert "▼ 4" in html and "-4" not in html


def _card(*, label: str = "Neutral", position: float = 50.0):
    from dashboard.presenters import RegimeCard

    return RegimeCard(label=label, accent="#FFD166", body="body copy", position=position)


# ── stylesheets ─────────────────────────────────────────────────────────────


STYLESHEETS = sorted(p.name for p in (TEMPLATE_DIR / "styles").glob("*.css"))


def test_stylesheets_are_shipped_alongside_the_templates() -> None:
    assert STYLESHEETS


@pytest.mark.parametrize("name", STYLESHEETS)
def test_every_stylesheet_loads_wrapped_in_a_style_tag(name: str) -> None:
    css = stylesheet(name)

    assert css.startswith("<style>") and css.endswith("</style>")
    assert "\n" not in css


@pytest.mark.parametrize("name", STYLESHEETS)
def test_every_stylesheet_has_balanced_braces(name: str) -> None:
    css = stylesheet(name)

    assert css.count("{") == css.count("}")


def test_a_missing_stylesheet_fails_loudly() -> None:
    with pytest.raises(FileNotFoundError):
        stylesheet("does-not-exist.css")
