from __future__ import annotations

from services.market.fmp_client import FMPClient
from tests.fakes import FakeSession


def test_fmp_client_normalizes_and_filters_price_rows() -> None:
    session = FakeSession(
        (
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
            },
            [
                {"date": "2024-01-03", "adjClose": "91.5"},
                {"date": "2024-01-02", "adjClose": "90.25"},
            ],
        )
    )
    client = FMPClient(api_key="key", base_url="https://example.test/", session=session)

    frame = client.get_historical_price_eod_full("ief", start="2024-01-03")

    assert list(frame["date"]) == ["2024-01-03"]
    assert frame["ticker"].iloc[0] == "IEF"
    assert float(frame["close"].iloc[0]) == 101.5
    assert float(frame["adj_close"].iloc[0]) == 91.5
    assert session.calls[0][0] == "https://example.test/historical-price-eod/full"
    assert session.calls[0][1]["apikey"] == "key"
    assert session.calls[1][0] == "https://example.test/historical-price-eod/dividend-adjusted"
    assert session.calls[1][1] == {
        "symbol": "ief",
        "from": "2024-01-03",
        "apikey": "key",
    }


def test_fmp_client_fetches_economic_calendar_with_date_window() -> None:
    payload = [{"date": "2026-05-08 08:30:00", "event": "Nonfarm Payrolls", "currency": "USD"}]
    session = FakeSession(payload)
    client = FMPClient(api_key="key", base_url="https://example.test/", session=session)

    rows = client.get_economic_calendar(start="2026-05-07", end="2026-05-21")

    assert rows == payload
    assert session.calls[0][0] == "https://example.test/economic-calendar"
    assert session.calls[0][1] == {
        "from": "2026-05-07",
        "to": "2026-05-21",
        "apikey": "key",
    }


def _client(*payloads: object) -> FMPClient:
    return FMPClient(
        api_key="key", base_url="https://example.test/", session=FakeSession(tuple(payloads))
    )


def test_a_symbol_with_no_rows_yields_an_empty_but_shaped_frame() -> None:
    frame = _client({"historical": []}).get_historical_price_eod_full("IEF")

    assert frame.empty
    assert {"date", "close", "adj_close", "ticker"} <= set(frame.columns)


def test_a_missing_adjusted_close_falls_back_to_the_raw_close() -> None:
    rows = [
        {"date": "2024-01-02", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 10}
    ]

    frame = _client({"historical": rows}, []).get_historical_price_eod_full("IEF")

    assert float(frame["adj_close"].iloc[0]) == 100.5


def test_rows_are_returned_in_date_order() -> None:
    rows = [
        {"date": d, "open": 1, "high": 1, "low": 1, "close": 1, "adjClose": 1, "volume": 1}
        for d in ("2024-01-05", "2024-01-02", "2024-01-03")
    ]

    frame = _client({"historical": rows}, []).get_historical_price_eod_full("IEF")

    assert list(frame["date"]) == ["2024-01-02", "2024-01-03", "2024-01-05"]


def test_rows_with_unusable_numbers_are_dropped() -> None:
    rows = [
        {"date": "2024-01-02", "open": "x", "high": "y", "low": "z", "close": "w", "volume": "v"},
        {
            "date": "2024-01-03",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "adjClose": 1,
            "volume": 1,
        },
    ]

    frame = _client({"historical": rows}, []).get_historical_price_eod_full("IEF")

    assert list(frame["date"]) == ["2024-01-03"]


def test_the_ticker_column_is_normalised_to_upper_case() -> None:
    rows = [
        {
            "date": "2024-01-02",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "adjClose": 1,
            "volume": 1,
        }
    ]

    frame = _client({"historical": rows}, []).get_historical_price_eod_full(" ief ".strip())

    assert set(frame["ticker"]) == {"IEF"}


def test_a_bare_list_payload_is_accepted_as_rows() -> None:
    rows = [
        {
            "date": "2024-01-02",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "adjClose": 1,
            "volume": 1,
        }
    ]

    frame = _client(rows, []).get_historical_price_eod_full("IEF")

    assert len(frame) == 1


def test_the_security_profile_unwraps_the_first_record() -> None:
    profile = _client([{"symbol": "IEF", "companyName": "iShares 7-10"}]).get_security_profile(
        "IEF"
    )

    assert profile["companyName"] == "iShares 7-10"


def test_an_empty_profile_payload_yields_an_empty_record() -> None:
    assert _client([]).get_security_profile("IEF") == {}


def test_etf_info_unwraps_the_first_record() -> None:
    assert _client([{"expenseRatio": 0.15}]).get_etf_info("IEF")["expenseRatio"] == 0.15


def test_holdings_are_returned_as_records() -> None:
    holdings = _client([{"asset": "T 4.5 2030", "weightPercentage": "1.2"}]).get_etf_holdings("IEF")

    assert holdings[0]["asset"] == "T 4.5 2030"


def test_an_empty_holdings_payload_yields_no_rows() -> None:
    assert _client([]).get_etf_holdings("IEF") == []


def test_the_api_key_is_attached_to_every_request() -> None:
    client = _client([])
    client.get_security_profile("IEF")

    assert client.session.calls[0][1]["apikey"] == "key"
