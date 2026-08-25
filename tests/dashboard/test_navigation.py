"""View switching. An <a href> cannot rerun Streamlit in place, so navigation is buttons."""

from __future__ import annotations

import pytest

from dashboard import navigation
from dashboard.navigation import ACTIVE_VIEW_KEY, DEFAULT_VIEW, VIEWS


class _Rerun(Exception):
    """Stands in for st.rerun, which halts the script run."""


class _FakeStreamlit:
    def __init__(self, query: dict[str, str] | None = None) -> None:
        self.session_state: dict[str, str] = {}
        self.query_params: dict[str, str] = query or {}

    def rerun(self) -> None:
        raise _Rerun


@pytest.fixture
def st(monkeypatch) -> _FakeStreamlit:
    fake = _FakeStreamlit()
    monkeypatch.setattr(navigation, "st", fake)
    return fake


def test_every_navigable_view_is_listed() -> None:
    assert VIEWS == ("Home", "Dashboard", "News", "Macro")


def test_the_first_render_lands_on_the_default_view(st: _FakeStreamlit) -> None:
    assert navigation.active_view() == DEFAULT_VIEW
    assert st.session_state[ACTIVE_VIEW_KEY] == DEFAULT_VIEW


def test_the_active_view_is_remembered_across_renders(st: _FakeStreamlit) -> None:
    st.session_state[ACTIVE_VIEW_KEY] = "Macro"

    assert navigation.active_view() == "Macro"


def test_switching_view_updates_state_and_reruns(st: _FakeStreamlit) -> None:
    with pytest.raises(_Rerun):
        navigation.go_to("Macro")

    assert st.session_state[ACTIVE_VIEW_KEY] == "Macro"


def test_switching_view_mirrors_into_the_url_so_a_refresh_stays_put(st: _FakeStreamlit) -> None:
    with pytest.raises(_Rerun):
        navigation.go_to("News")

    assert st.query_params["view"] == "news"


@pytest.mark.parametrize("requested", ["macro", "MACRO", "Macro", " macro "])
def test_a_view_query_parameter_is_adopted_however_it_is_cased(
    st: _FakeStreamlit, requested: str
) -> None:
    st.query_params["view"] = requested

    navigation.adopt_requested_view()

    assert st.session_state[ACTIVE_VIEW_KEY] == "Macro"


def test_an_unknown_view_parameter_is_ignored(st: _FakeStreamlit) -> None:
    st.query_params["view"] = "nonsense"

    navigation.adopt_requested_view()

    assert st.session_state[ACTIVE_VIEW_KEY] == DEFAULT_VIEW


def test_no_view_parameter_leaves_the_current_view_alone(st: _FakeStreamlit) -> None:
    st.session_state[ACTIVE_VIEW_KEY] = "News"

    navigation.adopt_requested_view()

    assert st.session_state[ACTIVE_VIEW_KEY] == "News"
