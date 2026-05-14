from __future__ import annotations

import asyncio

from services.market.finra_client import FINRAClient, USTCurve


class FakeResponse:
    def __init__(self, payload, text: str = "ok"):
        self.payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict | None, dict | None, int]] = []

    def post(
        self,
        url: str,
        *,
        auth=None,
        headers=None,
        json=None,
        timeout: int,
    ) -> FakeResponse:
        self.calls.append((url, auth, json, timeout))
        if "access_token" in url:
            return FakeResponse({"access_token": "token"})
        return FakeResponse([{"value": 1}])


def test_finra_client_posts_market_breadth_with_oauth() -> None:
    session = FakeSession()
    client = FINRAClient(client_id="id", client_secret="secret", session=session)

    frame = client.get_corporate_market_breadth(limit=7)

    assert frame.to_dict(orient="records") == [{"value": 1}]
    assert "access_token" in session.calls[0][0]
    assert session.calls[1][0] == (
        "https://api.finra.org/data/group/fixedIncomeMarket/name/corporateMarketBreadth"
    )
    assert session.calls[1][2] == {"limit": 7}


def test_finra_client_hidden_post_parses_stringified_rows() -> None:
    class HiddenSession:
        def post(self, url: str, *, headers=None, json=None, timeout: int) -> FakeResponse:
            return FakeResponse({"returnBody": {"data": '[{"cusip":"123456789"}]'}})

    client = FINRAClient(client_id="id", client_secret="secret")
    client._hidden_session = HiddenSession()
    client._xsrf_token = "xsrf"

    rows = client._hidden_post("CorporateAndAgencySecurities", {"limit": 1})

    assert rows == [{"cusip": "123456789"}]


def test_ust_curve_selects_nearest_benchmark_tenor() -> None:
    assert USTCurve.benchmark_tenor(0.1) == 0.25
    assert USTCurve.benchmark_tenor(5.3) == 5
    assert USTCurve.benchmark_tenor(8.8) == 10
    assert USTCurve.benchmark_tenor(25.0) == 20


def test_finra_client_routes_security_datasets_by_type() -> None:
    client = FINRAClient(client_id="id", client_secret="secret")

    assert client._security_dataset("corporate", "securities") == "CorporateAndAgencySecurities"
    assert client._security_dataset("corporate", "price_yield") == "EndOfDayPriceYield"
    assert client._security_dataset("treasury", "securities") == "TreasurySecurities"
    assert client._security_dataset("treasury", "price_yield") == "TreasuryEndOfDayPriceYield"
    assert client._security_dataset("treasury", "trade_history") == "TreasuryTradeActivity"


def test_finra_client_get_trade_history_supports_treasury_activity() -> None:
    calls = []

    class TestClient(FINRAClient):
        async def _ensure_fresh_session(self) -> None:
            return None

        def _hidden_post(self, endpoint: str, payload: dict) -> list[dict]:
            calls.append((endpoint, payload))
            return [
                {
                    "tradeTime": "17:29:56",
                    "benchmarkTermCode": "5Y",
                    "issueSymbolIdentifier": "TSRYS6371507",
                    "tradeStatus": "M",
                    "priceType": "D",
                    "reportingSideCode": "S",
                    "productSubTypeCode": "NOTE",
                    "contraPartyTypeCode": "A",
                    "tradeDate": "2026-05-13",
                    "reportedTradeVolume": "17000000.00",
                    "lastSaleYield": "4.122953",
                    "lastSalePrice": "98.896176",
                }
            ]

    client = TestClient(client_id="id", client_secret="secret")

    frame = asyncio.run(
        client.get_trade_history(
            "TSRYS6371507",
            start="2026-05-13",
            end="2026-05-13",
            limit=50,
            security_type="treasury",
        )
    )

    endpoint, payload = calls[0]
    assert endpoint == "TreasuryTradeActivity"
    assert payload["compareFilters"] == [
        {
            "fieldName": "issueSymbolIdentifier",
            "compareType": "EQUAL",
            "fieldValue": "TSRYS6371507",
        }
    ]
    assert payload["dateRangeFilters"][0]["fieldName"] == "tradeDate"
    assert payload["limit"] == 50
    assert float(frame["lastSalePrice"].iloc[0]) == 98.896176
