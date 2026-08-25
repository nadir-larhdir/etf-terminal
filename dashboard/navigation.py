"""In-app view navigation.

Every way of changing view goes through `go_to`, so the top nav and the inline calls to
action on a page share one mechanism: set session state, mirror it into the query string
so the view survives a refresh, and rerun. An `<a href>` cannot do this — it would reload
the whole Streamlit app (or open a tab), which is why the links are buttons.
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

VIEWS = ("Home", "Dashboard", "News", "Macro")
ACTIVE_VIEW_KEY = "active_view"
DEFAULT_VIEW = "Home"


def active_view() -> str:
    """Return the current view, initialising it on first render."""
    if ACTIVE_VIEW_KEY not in st.session_state:
        st.session_state[ACTIVE_VIEW_KEY] = DEFAULT_VIEW
    return str(st.session_state[ACTIVE_VIEW_KEY])


def go_to(view: str) -> None:
    """Switch to another view in place and rerun."""
    st.session_state[ACTIVE_VIEW_KEY] = view
    st.query_params["view"] = view.lower()
    st.rerun()


def adopt_requested_view() -> None:
    """Adopt a `?view=` query parameter, so a shared or refreshed URL lands correctly."""
    current = active_view()
    requested = str(st.query_params.get("view", "")).strip().title()
    if requested in VIEWS and requested != current:
        st.session_state[ACTIVE_VIEW_KEY] = requested


def nav_button(
    label: str,
    view: str,
    *,
    key: str,
    type: Literal["primary", "secondary", "tertiary"] = "tertiary",
    use_container_width: bool = False,
) -> None:
    """Render a button that switches view when clicked.

    Wrapped in a keyed container so a stylesheet can target `.st-key-<key>` and make the
    button read as the inline link it replaces.
    """
    with st.container(key=key):
        if st.button(
            label, key=f"{key}_button", type=type, use_container_width=use_container_width
        ):
            go_to(view)
