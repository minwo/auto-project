from __future__ import annotations

from datetime import date

from app.collectors.market_warnings import parse_market_warning_rows


def test_parse_market_warning_csv_maps_korean_columns() -> None:
    records = parse_market_warning_rows(
        [
            {
                "종목코드": "5930",
                "경보유형": "시장경보",
                "경보수준": "투자경고",
                "거래정지": "아니오",
                "관리종목": "예",
                "출처": "https://example.com",
            }
        ],
        trade_date=date(2026, 4, 29),
    )

    assert len(records) == 1
    assert records[0].trade_date == date(2026, 4, 29)
    assert records[0].code == "005930"
    assert records[0].warning_type == "시장경보"
    assert records[0].warning_level == "warning"
    assert records[0].is_halted is False
    assert records[0].is_under_management is True
    assert records[0].source_url == "https://example.com"


def test_parse_market_warning_csv_uses_row_trade_date() -> None:
    records = parse_market_warning_rows(
        [
            {
                "trade_date": "2026-04-30",
                "code": "123456",
                "warning_type": "risk",
                "warning_level": "danger",
                "is_halted": "true",
                "is_under_management": "false",
            }
        ]
    )

    assert len(records) == 1
    assert records[0].trade_date == date(2026, 4, 30)
    assert records[0].warning_level == "danger"
    assert records[0].is_halted is True
