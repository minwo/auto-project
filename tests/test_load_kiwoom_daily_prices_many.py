from __future__ import annotations

import pytest

from app.scripts.load_kiwoom_daily_prices_many import parse_code_list, parse_code_metadata_text, parse_code_text


def test_parse_code_list_normalizes_deduplicates_and_preserves_order() -> None:
    codes = parse_code_list("5930, 000660\n005930 035420")

    assert codes == ["005930", "000660", "035420"]


def test_parse_code_list_rejects_invalid_code() -> None:
    with pytest.raises(ValueError, match="invalid stock code"):
        parse_code_list("005930 abc")


def test_parse_code_text_allows_comments_commas_and_whitespace() -> None:
    text = "\n".join(
        [
            "# large caps",
            "005930, 000660",
            "035420  # NAVER",
            "005930",
        ]
    )

    assert parse_code_text(text) == ["005930", "000660", "035420"]


def test_parse_code_metadata_text_uses_single_code_comment_as_name() -> None:
    text = "\n".join(
        [
            "005930  # 삼성전자",
            "000660, 035420  # ignored for multi-code lines",
        ]
    )

    records = parse_code_metadata_text(text)

    assert [(item.code, item.name) for item in records] == [
        ("005930", "삼성전자"),
        ("000660", None),
        ("035420", None),
    ]
