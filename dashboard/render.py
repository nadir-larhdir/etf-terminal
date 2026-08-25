"""Template rendering for dashboard markup.

Markup lives in `dashboard/templates/*.html` rather than in f-strings, so it is escaped by
default, reviewable as HTML, and testable without a Streamlit runtime. `render` returns a
string; the caller decides whether to hand it to `st.markdown`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _build_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default_for_string=True, default=True),
        # A missing variable is a template bug; fail loudly instead of rendering "".
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


ENVIRONMENT = _build_environment()


def stylesheet(name: str) -> Markup:
    """Return a stylesheet from dashboard/templates/styles wrapped in a <style> tag."""
    css = (TEMPLATE_DIR / "styles" / name).read_text(encoding="utf-8")
    return Markup(f"<style>{' '.join(css.split())}</style>")


def render(template_name: str, **context: Any) -> Markup:
    """Render a template from dashboard/templates to a single-line HTML fragment.

    Streamlit's markdown parser treats an indented line as a code block, so the output is
    collapsed to one line. The result is `Markup` so a fragment can be composed into
    another template without being escaped a second time; values interpolated *inside* a
    template are still escaped normally.
    """
    html = ENVIRONMENT.get_template(template_name).render(**context)
    return Markup(" ".join(html.split()))
