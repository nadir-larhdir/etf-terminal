from __future__ import annotations

from services.macro.fred_client import FredClient


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[tuple[str, dict, int]] = []

    def get(self, url: str, *, params: dict, timeout: int) -> FakeResponse:
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payload)


def test_fred_client_uses_session_and_cleans_observations() -> None:
    session = FakeSession(
        {
            "observations": [
                {"date": "2024-01-02", "value": "4.25"},
                {"date": "2024-01-03", "value": "."},
            ]
        }
    )
    client = FredClient(api_key="key", base_url="https://fred.test/", session=session)

    frame = client.get_series("DGS10", start="2024-01-01", end="2024-01-04")

    assert list(frame["date"]) == ["2024-01-02"]
    assert float(frame["value"].iloc[0]) == 4.25
    assert frame["series_id"].iloc[0] == "DGS10"
    assert session.calls[0][0] == "https://fred.test/series/observations"
    assert session.calls[0][1]["api_key"] == "key"
