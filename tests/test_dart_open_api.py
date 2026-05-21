from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from app.collectors.dart_open_api import parse_corp_code_zip, parse_disclosure_list_payload


def _corp_code_zip(xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("CORPCODE.xml", xml)
    return buffer.getvalue()


def test_parse_corp_code_zip_maps_listed_records() -> None:
    payload = _corp_code_zip(
        """
        <result>
          <list>
            <corp_code>00126380</corp_code>
            <corp_name>Samsung Electronics</corp_name>
            <stock_code>005930</stock_code>
            <modify_date>20240101</modify_date>
          </list>
          <list>
            <corp_code>99999999</corp_code>
            <corp_name>Unlisted</corp_name>
            <stock_code> </stock_code>
          </list>
        </result>
        """
    )

    records = parse_corp_code_zip(payload)

    assert len(records) == 2
    assert records[0].corp_code == "00126380"
    assert records[0].stock_code == "005930"
    assert records[1].stock_code is None


def test_parse_disclosure_list_payload_maps_rows_and_material_tag() -> None:
    payload = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380",
                "stock_code": "005930",
                "rcept_no": "20260429000001",
                "report_nm": "single sales agreement",
                "rcept_dt": "20260429",
            }
        ],
    }

    records = parse_disclosure_list_payload(payload, trade_date=date(2026, 4, 29))

    assert len(records) == 1
    assert records[0].code == "005930"
    assert records[0].receipt_no == "20260429000001"
    assert records[0].is_material is True
    assert records[0].material_tag == "contract"


def test_parse_disclosure_list_payload_detects_korean_material_keywords() -> None:
    payload = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380",
                "stock_code": "005930",
                "rcept_no": "20260429000002",
                "report_nm": "신규시설투자등",
                "rcept_dt": "20260429",
            }
        ],
    }

    records = parse_disclosure_list_payload(payload, trade_date=date(2026, 4, 29))

    assert len(records) == 1
    assert records[0].is_material is True


def test_parse_disclosure_list_payload_prefers_disclosure_classification_code() -> None:
    payload = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380",
                "stock_code": "005930",
                "rcept_no": "20260429000003",
                "report_nm": "정정신고",
                "rcept_dt": "20260429",
                "report_cd": "C001",
            },
            {
                "corp_code": "00126380",
                "stock_code": "005930",
                "rcept_no": "20260429000004",
                "report_nm": "기타 신고",
                "rcept_dt": "20260429",
                "pblntf_detail_ty": "I001",
            },
        ],
    }

    records = parse_disclosure_list_payload(payload, trade_date=date(2026, 4, 29))

    assert [record.material_tag for record in records] == ["contract", "dilution"]
    assert all(record.is_material for record in records)


def test_parse_disclosure_list_payload_returns_empty_on_no_data() -> None:
    records = parse_disclosure_list_payload({"status": "013", "message": "no data"}, trade_date=date(2026, 4, 29))

    assert records == []


def test_parse_disclosure_list_payload_raises_on_error() -> None:
    with pytest.raises(RuntimeError, match="invalid key"):
        parse_disclosure_list_payload({"status": "010", "message": "invalid key"}, trade_date=date(2026, 4, 29))
