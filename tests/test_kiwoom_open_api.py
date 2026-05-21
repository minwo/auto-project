from __future__ import annotations

from datetime import date

import pytest

from app.collectors.kiwoom_open_api import parse_kiwoom_daily_price_records, parse_kiwoom_index_daily_price_records


def test_parse_kiwoom_daily_price_records_maps_rows() -> None:
    payload = {
        "return_code": 0,
        "stock_name": "삼성전자",
        "data": [
            {
                "dt": "20260429",
                "open_pric": "55000",
                "high_pric": "56000",
                "low_pric": "54500",
                "close_pric": "55800",
                "trde_qty": "12000000",
                "trde_prica": "667800",
            }
        ],
    }

    records = parse_kiwoom_daily_price_records(payload, requested_code="005930")

    assert len(records) == 1
    record = records[0]
    assert record.trade_date == date(2026, 4, 29)
    assert record.code == "005930"
    assert record.name_kr == "삼성전자"
    assert record.close_price == 55800.0
    assert record.turnover == 667800000000.0


def test_parse_kiwoom_daily_price_records_raises_on_error_response() -> None:
    payload = {"return_code": 500, "return_msg": "invalid token"}

    with pytest.raises(RuntimeError, match="Kiwoom API error 500: invalid token"):
        parse_kiwoom_daily_price_records(payload, requested_code="005930")


def test_parse_kiwoom_daily_price_records_cleans_null_padded_error_message() -> None:
    payload = {"return_code": 8050, "return_msg": "\uc778\x00\uc99d\x00 \uc2e4\x00\ud328"}

    with pytest.raises(RuntimeError) as exc_info:
        parse_kiwoom_daily_price_records(payload, requested_code="005930")

    message = str(exc_info.value)
    assert "\x00" not in message
    assert message == "Kiwoom API error 8050: \uc778\uc99d \uc2e4\ud328"


def test_parse_kiwoom_daily_price_records_rejects_invalid_ohlc() -> None:
    payload = {
        "return_code": 0,
        "data": [
            {
                "dt": "20260430",
                "open_pric": "149800",
                "high_pric": "148000",
                "low_pric": "143500",
                "close_pric": "146200",
                "trde_qty": "1134227",
                "trde_prica": "165395",
            }
        ],
    }

    with pytest.raises(ValueError, match="open 149800.0 is outside"):
        parse_kiwoom_daily_price_records(payload, requested_code="096770")


def test_parse_kiwoom_index_daily_price_records_normalizes_implied_decimals() -> None:
    payload = {
        "inds_cd": "001",
        "inds_dt_pole_qry": [
            {
                "dt": "20260430",
                "open_pric": "251064",
                "high_pric": "252733",
                "low_pric": "249918",
                "cur_prc": "252127",
                "trde_qty": "393564",
                "trde_prica": "10582466",
            }
        ],
        "return_code": 0,
    }

    records = parse_kiwoom_index_daily_price_records(
        payload,
        requested_index_code="001",
        output_code="KOSPI",
        name_kr="KOSPI",
    )

    assert len(records) == 1
    record = records[0]
    assert record.trade_date == date(2026, 4, 30)
    assert record.code == "KOSPI"
    assert record.market == "INDEX"
    assert record.sector == "INDEX"
    assert record.open_price == 2510.64
    assert record.close_price == 2521.27
    assert record.source == "kiwoom_index_open_api"
