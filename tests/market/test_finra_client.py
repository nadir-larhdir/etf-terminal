from __future__ import annotations

from services.market.finra_client import FINRAClient


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
