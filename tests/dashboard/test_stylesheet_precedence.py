"""Guards for CSS rules that only work if they outrank an earlier, broader rule.

The dashboard styles Streamlit's own widgets, so a call-to-action rule competes with the
global button rule. Both use !important, which makes specificity the decider — and that
is invisible until it is rendered, so it is asserted here instead.
"""

from __future__ import annotations

import re

import pytest

from dashboard.render import TEMPLATE_DIR

THEME = (TEMPLATE_DIR / "styles" / "theme.css").read_text(encoding="utf-8")

GLOBAL_BUTTON_RULE = "div.stButton > button"
CTA_PREFIX = "st-key-home_cta_"


def specificity(selector: str) -> tuple[int, int, int]:
    """Return (ids, classes, elements) for one selector, per the CSS cascade."""
    selector = re.sub(r"::?[a-z-]+(\([^)]*\))?", "", selector)  # pseudo-elements/classes
    ids = len(re.findall(r"#[\w-]+", selector))
    classes = len(re.findall(r"\.[\w-]+", selector)) + len(re.findall(r"\[[^\]]+\]", selector))
    stripped = re.sub(r"[.#\[][^\s>+~]*", " ", selector)
    elements = len(re.findall(r"\b[a-z][\w-]*\b", stripped))
    return ids, classes, elements


def selectors_for(rule_fragment: str) -> list[str]:
    """Every selector in the stylesheet whose declaration block mentions the fragment."""
    found: list[str] = []
    for block in re.finditer(r"([^{}]+)\{([^}]*)\}", THEME):
        selector_text = block.group(1)
        selector_text = re.sub(r"/\*.*?\*/", "", selector_text, flags=re.S).strip()
        if rule_fragment in selector_text:
            found.extend(s.strip() for s in selector_text.split(",") if s.strip())
    return found


def test_the_global_button_rule_is_still_the_one_being_competed_with() -> None:
    assert GLOBAL_BUTTON_RULE in THEME


def test_the_call_to_action_rules_outrank_the_global_button_rule() -> None:
    """This is why the links rendered black: 0-1-1 lost to the global rule's 0-1-2."""
    baseline = specificity(GLOBAL_BUTTON_RULE)
    cta = [s for s in selectors_for(CTA_PREFIX) if "button" in s]

    assert cta, "no call-to-action button selectors found"
    for selector in cta:
        assert specificity(selector) > baseline, f"{selector} does not outrank {GLOBAL_BUTTON_RULE}"


def test_the_call_to_action_colour_targets_the_label_node_not_only_the_button() -> None:
    """Streamlit renders the label in its own element, so the button alone is not enough."""
    assert any(s.rstrip().endswith("*") for s in selectors_for(CTA_PREFIX))


def test_the_link_colour_comes_from_a_named_token() -> None:
    assert "--etf-link:" in THEME
    assert "color: var(--etf-link) !important" in THEME


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("div.stButton > button", (0, 1, 2)),
        ('[class*="st-key-x"] button', (0, 1, 1)),
        ('[class*="st-key-x"][class*="st-key-x"] button', (0, 2, 1)),
        ('[class*="st-key-x"][class*="st-key-x"] button *', (0, 2, 1)),
        ("#id .cls div", (1, 1, 1)),
    ],
)
def test_the_specificity_calculator_matches_the_cascade_rules(
    selector: str, expected: tuple[int, int, int]
) -> None:
    assert specificity(selector) == expected
