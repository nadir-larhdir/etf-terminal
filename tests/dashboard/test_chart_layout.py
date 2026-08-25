"""Shared Plotly layout helpers and the perf timing context."""

from __future__ import annotations

import logging

import pytest

from dashboard.mobile import PLOTLY_CHART_CONFIG, _responsive_legend, responsive_chart_layout
from dashboard.perf import timed_block


def _layout(**overrides: object) -> dict:
    kwargs: dict[str, object] = {"height": 400, "font_family": "monospace"}
    kwargs.update(overrides)
    return responsive_chart_layout("Title", **kwargs)  # type: ignore[arg-type]


# ── chart config ────────────────────────────────────────────────────────────


def test_the_mode_bar_is_hidden_and_charts_stay_responsive() -> None:
    assert PLOTLY_CHART_CONFIG["displayModeBar"] is False
    assert PLOTLY_CHART_CONFIG["responsive"] is True


def test_scroll_zoom_is_disabled_so_the_page_scrolls_over_a_chart() -> None:
    assert PLOTLY_CHART_CONFIG["scrollZoom"] is False


# ── responsive legend ───────────────────────────────────────────────────────


@pytest.mark.parametrize("height", [300, 380, 460, 800])
def test_the_legend_is_always_horizontal_and_centred(height: int) -> None:
    legend = _responsive_legend(height)

    assert legend["orientation"] == "h"
    assert legend["xanchor"] == "center" and legend["x"] == 0.5


def test_a_shorter_chart_gets_smaller_legend_text() -> None:
    tall = _responsive_legend(500)["font"]["size"]
    short = _responsive_legend(300)["font"]["size"]

    assert short < tall


def test_a_shorter_chart_lifts_its_legend_further_clear_of_the_plot() -> None:
    assert _responsive_legend(300)["y"] > _responsive_legend(500)["y"]


def test_legend_font_size_never_collapses_to_nothing() -> None:
    for height in (100, 250, 400, 900):
        assert _responsive_legend(height)["font"]["size"] > 0


# ── chart layout ────────────────────────────────────────────────────────────


def test_the_layout_carries_the_title_and_height_it_was_given() -> None:
    layout = _layout(height=420)

    assert layout["title"]["text"] == "Title"
    assert layout["height"] == 420


def test_a_y_axis_title_is_applied_when_supplied() -> None:
    assert _layout(yaxis_title="bps")["yaxis"]["title"] == "bps"


def test_the_layout_supplies_a_legend_by_default() -> None:
    assert _layout()["legend"]["orientation"] == "h"


def test_an_explicit_legend_overrides_the_responsive_default() -> None:
    layout = _layout(legend={"orientation": "v"})

    assert layout["legend"]["orientation"] == "v"


def test_the_configured_font_family_is_applied() -> None:
    assert "monospace" in _layout(font_family="monospace")["font"]["family"]


def test_an_explicit_margin_overrides_the_default() -> None:
    layout = _layout(margin={"l": 1, "r": 2, "t": 3, "b": 4})

    assert layout["margin"]["l"] == 1


def test_axis_overrides_are_merged_into_the_layout() -> None:
    layout = _layout(xaxis={"showgrid": True})

    assert layout["xaxis"]["showgrid"] is True


# ── perf timing ─────────────────────────────────────────────────────────────


def test_a_timed_block_logs_its_label_and_elapsed_time(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="etf_terminal.perf"), timed_block("load.prices"):
        pass

    assert "load.prices took" in caplog.text


def test_a_timed_block_still_logs_when_the_body_raises(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="etf_terminal.perf"):
        with pytest.raises(ValueError), timed_block("load.prices"):
            raise ValueError("boom")

    assert "load.prices took" in caplog.text


def test_a_timed_block_does_not_swallow_the_exception() -> None:
    with pytest.raises(ValueError, match="boom"), timed_block("load.prices"):
        raise ValueError("boom")
