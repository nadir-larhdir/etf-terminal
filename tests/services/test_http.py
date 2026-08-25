from __future__ import annotations

import pytest
import requests

from services.http import ApiError, JsonApiClient, RetryPolicy


class _Response:
    def __init__(self, payload=None, *, error: Exception | None = None):
        self._payload = payload
        self._error = error

    def raise_for_status(self) -> None:
        return None

    def json(self):
        if self._error is not None:
            raise self._error
        return self._payload


class _Session:
    """Records calls and returns queued responses, or raises a queued exception."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict, int]] = []

    def get(self, url: str, *, params: dict, timeout: int):
        self.calls.append((url, params, timeout))
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _client(session, **kwargs) -> JsonApiClient:
    return JsonApiClient(base_url="https://vendor.test/", session=session, **kwargs)


def test_base_url_trailing_slash_does_not_double_up_on_the_endpoint() -> None:
    session = _Session(_Response({"ok": True}))

    _client(session).get_json("/series/observations")

    assert session.calls[0][0] == "https://vendor.test/series/observations"


def test_default_params_are_merged_into_every_request() -> None:
    class Authed(JsonApiClient):
        def default_params(self) -> dict[str, str]:
            return {"api_key": "secret"}

    session = _Session(_Response({}))

    Authed(base_url="https://vendor.test", session=session).get_json("x", {"series_id": "DGS10"})

    assert session.calls[0][1] == {"series_id": "DGS10", "api_key": "secret"}


def test_default_params_win_over_a_caller_supplied_collision() -> None:
    class Authed(JsonApiClient):
        def default_params(self) -> dict[str, str]:
            return {"api_key": "real"}

    session = _Session(_Response({}))

    Authed(base_url="https://vendor.test", session=session).get_json("x", {"api_key": "spoofed"})

    assert session.calls[0][1]["api_key"] == "real"


def test_the_configured_timeout_is_applied() -> None:
    session = _Session(_Response({}))

    _client(session, timeout=7).get_json("x")

    assert session.calls[0][2] == 7


def test_transport_failures_surface_as_a_typed_api_error() -> None:
    session = _Session(requests.ConnectionError("connection refused"))

    with pytest.raises(ApiError) as excinfo:
        _client(session, service_name="FRED").get_json("series")

    assert "FRED series failed" in str(excinfo.value)
    assert excinfo.value.status_code is None


def test_http_status_errors_carry_the_status_code() -> None:
    response = requests.Response()
    response.status_code = 503
    session = _Session(requests.HTTPError("503 Server Error", response=response))

    with pytest.raises(ApiError) as excinfo:
        _client(session).get_json("series")

    assert excinfo.value.status_code == 503


def test_a_non_json_body_is_reported_rather_than_raising_a_value_error() -> None:
    session = _Session(_Response(error=ValueError("Expecting value")))

    with pytest.raises(ApiError, match="invalid JSON body"):
        _client(session).get_json("series")


def test_an_injected_session_is_used_verbatim() -> None:
    session = _Session(_Response({"ok": True}))

    assert _client(session).session is session


def test_a_self_built_session_mounts_the_retry_adapter_on_both_schemes() -> None:
    client = JsonApiClient(base_url="https://vendor.test")

    for scheme in ("https://", "http://"):
        assert client.session.get_adapter(scheme).max_retries.total == RetryPolicy().attempts


def test_retry_policy_only_retries_idempotent_gets_on_transient_statuses() -> None:
    retry = RetryPolicy(attempts=5, backoff_factor=0.25).to_urllib3()

    assert retry.total == 5
    assert retry.backoff_factor == 0.25
    assert set(retry.allowed_methods or ()) == {"GET"}
    assert 503 in retry.status_forcelist and 404 not in retry.status_forcelist
