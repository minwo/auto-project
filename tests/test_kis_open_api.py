from __future__ import annotations

from datetime import date

import pytest

from app.collectors.kis_open_api import parse_kis_daily_price_records


def test_parse_kis_daily_price_records_maps_rows() -> None:
    payload = {
        "rt_cd": "0",
        "output1": {
            "hts_kor_isnm": "삼성전자",
            "bstp_kor_isnm": "전기전자",
            "rprs_mrkt_kor_name": "KOSPI",
        },
        "output2": [
            {
                "stck_bsop_date": "20260424",
                "stck_oprc": "55000",
                "stck_hgpr": "56000",
                "stck_lwpr": "54500",
                "stck_clpr": "55800",
                "acml_vol": "12000000",
                "acml_tr_pbmn": "667800000000",
            }
        ],
    }

    records = parse_kis_daily_price_records(payload, requested_code="005930", market_code="J")

    assert len(records) == 1
    record = records[0]
    assert record.trade_date == date(2026, 4, 24)
    assert record.code == "005930"
    assert record.name_kr == "삼성전자"
    assert record.market == "KOSPI"
    assert record.sector == "전기전자"
    assert record.close_price == 55800.0
    assert record.turnover == 667800000000.0


def test_parse_kis_daily_price_records_raises_on_error_response() -> None:
    payload = {"rt_cd": "1", "msg1": "invalid token"}

    with pytest.raises(RuntimeError, match="invalid token"):
        parse_kis_daily_price_records(payload, requested_code="005930", market_code="J")
