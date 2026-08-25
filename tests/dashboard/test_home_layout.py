"""Layout invariants for the homepage that are otherwise only visible in a browser."""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from dashboard.pages.home_page import CONTENT_SPLIT
from dashboard.render import TEMPLATE_DIR

SOURCE = pathlib.Path("dashboard/pages/home_page.py").read_text(encoding="utf-8")
THEME = (TEMPLATE_DIR / "styles" / "theme.css").read_text(encoding="utf-8")


def _column_calls() -> list[ast.Call]:
    tree = ast.parse(SOURCE)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "columns"
    ]


def test_the_page_is_one_two_column_layout() -> None:
    """A single row makes alignment structural: the content column and the rail cannot
    drift apart the way two rows with different ratios did."""
    split_rows = [
        call
        for call in _column_calls()
        if call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == "CONTENT_SPLIT"
    ]

    assert len(split_rows) == 1, "the page should use one content/rail row, not one per band"


def test_the_rail_follows_the_regime_card_in_the_same_column() -> None:
    """Market Pulse sits directly under the regime card, with no spacer holding it down."""
    tree = ast.parse(SOURCE)
    render_fn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "render"
    )
    rail = next(
        item
        for item in ast.walk(render_fn)
        if isinstance(item, ast.withitem)
        and isinstance(item.context_expr, ast.Name)
        and item.context_expr.id == "rail_col"
    )
    body = next(
        node.body
        for node in ast.walk(render_fn)
        if isinstance(node, ast.With) and rail in node.items
    )

    assert len(body) == 3, "rail holds the regime card, the pulse card and the built-for card"
    assert "home-right-rail" not in SOURCE


def test_no_two_column_row_hardcodes_its_own_ratio() -> None:
    for call in _column_calls():
        first = call.args[0] if call.args else None
        if isinstance(first, ast.List):  # a literal ratio rather than the shared constant
            raise AssertionError(f"hardcoded column ratio at line {call.lineno}")


def test_the_split_favours_the_content_column() -> None:
    left, right = CONTENT_SPLIT

    assert left > right
    assert left / (left + right) == pytest.approx(0.697, abs=0.01)


def test_copy_that_ends_a_card_reserves_space_below_the_last_line() -> None:
    """A card ending in copy has nothing after it to hold the last line off the border.

    The spacing lives on the copy element rather than the container because the container
    is a Streamlit bordered block whose padding is generated at runtime.
    """
    rule = re.search(r"\.home-context-body--tail \{([^}]*)\}", THEME)

    assert rule is not None
    assert re.search(r"padding-bottom:\s*0?\.\d+rem", rule.group(1))


# ── card rhythm ─────────────────────────────────────────────────────────────

RAIL_CARDS = (".home-regime-card", ".home-built-card", '[class*="st-key-home_card_"]')


def _declarations(selector: str) -> dict[str, str]:
    """The declarations of the rule whose selector list contains `selector`."""
    for block in re.finditer(r"([^{}]+)\{([^}]*)\}", THEME):
        selectors = re.sub(r"/\*.*?\*/", "", block.group(1), flags=re.S)
        if any(part.strip() == selector for part in selectors.split(",")):
            return {
                k.strip(): v.strip().replace("!important", "").strip()
                for k, v in (d.split(":", 1) for d in block.group(2).split(";") if ":" in d)
            }
    raise AssertionError(f"no rule for {selector}")


def test_every_card_shares_one_padding() -> None:
    """Cards rendered by markdown and by a Streamlit container must look identical."""
    paddings = {_declarations(sel).get("padding") for sel in RAIL_CARDS}

    assert len(paddings) == 1, f"cards disagree on padding: {paddings}"


def test_no_card_carries_its_own_vertical_margin() -> None:
    """Spacing in the rail comes from Streamlit's single gap between block children.
    A margin on one card is what made Built-for sit further from Market Pulse than
    Market Pulse sat from the regime card."""
    for selector in RAIL_CARDS:
        declarations = _declarations(selector)
        for prop in ("margin", "margin-top", "margin-bottom"):
            assert prop not in declarations, f"{selector} sets {prop}"


def test_only_the_side_by_side_cards_are_stretched_to_equal_height() -> None:
    """A stacked card stretched to 100% swallows the gap beneath it."""
    for selector in RAIL_CARDS:
        assert "height" not in _declarations(selector), f"{selector} is stretched"

    assert "st-key-home_card_context_" in THEME


# ── one vertical rhythm ─────────────────────────────────────────────────────

COLUMN_BLOCKS = ("home_content", "home_rail")  # container keys; CSS sees them as st-key-*
# Blocks that sit directly in a page column: their spacing must come from the column gap.
COLUMN_LEVEL = (".home-market-strip", ".home-stat-grid", ".home-section-title")


def test_both_page_columns_are_keyed_so_one_rule_owns_their_spacing() -> None:
    for key in COLUMN_BLOCKS:
        assert f'key="{key}"' in SOURCE, f"{key} container missing from the page"
        assert f"st-key-{key}" in THEME, f"{key} has no spacing rule"


def test_the_column_gap_is_set_explicitly_from_a_single_token() -> None:
    """Left to Streamlit's default and then fought with per-element margins, the gaps
    came out uneven: 5px under the regime card, 22px under Market Pulse."""
    assert "--etf-section-gap:" in THEME

    rule = re.search(
        r'\[class\*="st-key-home_content"\],\s*\[class\*="st-key-home_rail"\] \{([^}]*)\}',
        THEME,
    )
    assert rule is not None, "no shared gap rule for the page columns"
    assert "gap: var(--etf-section-gap)" in rule.group(1)


def test_the_gap_targets_the_flex_container_not_its_children() -> None:
    """Streamlit puts the key class on the flex container itself. A `> div` selector sets
    the gap on the children instead, which does nothing to the column and is invisible."""
    for column in ("st-key-home_content", "st-key-home_rail"):
        assert f'[class*="{column}"] > div {{' not in THEME
        assert f'[class*="{column}"] > div,' not in THEME


def test_no_column_level_block_adds_to_the_gap() -> None:
    for selector in COLUMN_LEVEL:
        for match in re.finditer(re.escape(selector) + r" \{([^}]*)\}", THEME):
            for prop, value in re.findall(r"(margin[a-z-]*):\s*([^;]+)", match.group(1)):
                normalised = value.replace("0", "").replace("rem", "").strip(" ;")
                assert (
                    not normalised or "var(--etf-section-gap)" in value
                ), f"{selector} sets {prop}: {value}, which adds to the column gap"
