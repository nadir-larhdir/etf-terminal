from __future__ import annotations

from services.market.fmp_client import FMPClient


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


def test_fmp_client_normalizes_and_filters_price_rows() -> None:
    session = FakeSession(
        {
            "historical": [
                {
                    "date": "2024-01-03",
                    "open": "101",
                    "high": "102",
                    "low": "100",
                    "close": "101.5",
                    "volume": "1200",
                },
                {
                    "date": "2024-01-02",
                    "open": "100",
                    "high": "101",
                    "low": "99",
                    "close": "100.5",
                    "adjClose": "100.25",
                    "volume": "1000",
                },
            ]
        }
    )
    client = FMPClient(api_key="key", base_url="https://example.test/", session=session)

    frame = client.get_historical_price_eod_full("ief", start="2024-01-03")

    assert list(frame["date"]) == ["2024-01-03"]
    assert frame["ticker"].iloc[0] == "IEF"
    assert float(frame["adj_close"].iloc[0]) == 101.5
    assert session.calls[0][0] == "https://example.test/historical-price-eod/full"
    assert session.calls[0][1]["apikey"] == "key"
