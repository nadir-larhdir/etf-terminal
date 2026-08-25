"""Shared JSON REST client: one session, bounded retries, uniform timeouts and errors.

Every outbound data call in the app goes through `JsonApiClient`, so retry behaviour and
failure reporting are defined once instead of per vendor. Retries come from urllib3's
`Retry` rather than a hand-rolled loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_TIMEOUT_SECONDS = 30


class ApiError(RuntimeError):
    """A vendor API call failed, or returned a body that was not JSON."""

    def __init__(
        self, service: str, endpoint: str, message: str, *, status_code: int | None = None
    ) -> None:
        super().__init__(f"{service} {endpoint} failed: {message}")
        self.service = service
        self.endpoint = endpoint
        self.status_code = status_code


@dataclass(frozen=True)
class RetryPolicy:
    """How many times, and on what, to retry an idempotent GET."""

    attempts: int = 3
    backoff_factor: float = 0.5
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504)

    def to_urllib3(self) -> Retry:
        """Build the urllib3 Retry that the HTTP adapter enforces."""
        return Retry(
            total=self.attempts,
            backoff_factor=self.backoff_factor,
            status_forcelist=list(self.status_forcelist),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )


@dataclass
class JsonApiClient:
    """Base class for read-only JSON APIs.

    A caller-supplied `session` is used as-is so tests can inject a double; a session we
    create ourselves gets the retry adapter mounted on it.
    """

    base_url: str
    session: Any = None
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    service_name: str = "api"

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if self.session is None:
            self.session = self._build_session()

    def default_params(self) -> dict[str, str]:
        """Parameters merged into every request, typically credentials. Override in subclasses."""
        return {}

    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """GET an endpoint and return the decoded JSON body."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        merged = {**(params or {}), **self.default_params()}
        try:
            response = self.session.get(url, params=merged, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            raise ApiError(self.service_name, endpoint, str(exc), status_code=status) from exc
        except requests.RequestException as exc:
            raise ApiError(self.service_name, endpoint, str(exc)) from exc
        except ValueError as exc:
            raise ApiError(self.service_name, endpoint, f"invalid JSON body: {exc}") from exc

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=self.retry.to_urllib3())
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session
