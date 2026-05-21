from __future__ import annotations

from datetime import date

from app.collectors.naver_news import clean_news_text, parse_naver_news_payload


def test_clean_news_text_removes_html_and_entities() -> None:
    assert clean_news_text("<b>LG화학</b> &amp; 수주") == "LG화학 & 수주"


def test_parse_naver_news_payload_maps_and_classifies_records() -> None:
    payload = {
        "items": [
            {
                "title": "<b>LG화학</b>, 대규모 공급계약 체결",
                "originallink": "https://news.example.com/article/1",
                "description": "배터리 소재 공급계약",
                "pubDate": "Mon, 04 May 2026 10:00:00 +0900",
            },
            {
                "title": "전일 뉴스는 제외",
                "originallink": "https://news.example.com/article/2",
                "description": "old",
                "pubDate": "Sun, 03 May 2026 10:00:00 +0900",
            },
        ]
    }

    records = parse_naver_news_payload(payload, trade_date=date(2026, 5, 4), code="051910")

    assert len(records) == 1
    assert records[0].code == "051910"
    assert records[0].news_type == "contract"
    assert records[0].trust_score > 0.5
    assert records[0].source == "news.example.com"


def test_parse_naver_news_payload_marks_risk_news() -> None:
    payload = {
        "items": [
            {
                "title": "관리종목 지정 우려",
                "originallink": "https://risk.example.com/article/1",
                "description": "거래정지 가능성",
                "pubDate": "Mon, 04 May 2026 11:00:00 +0900",
            },
        ]
    }

    records = parse_naver_news_payload(payload, trade_date=date(2026, 5, 4), code="123456")

    assert records[0].news_type == "trading_risk"
