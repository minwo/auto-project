from app.collectors.krx_master import StockMasterRecord, _to_record


def test_to_record_strips_krx_short_code_prefix() -> None:
    record = _to_record(
        {
            "basDt": "20260429",
            "srtnCd": "A440110",
            "isinCd": "KR7440110006",
            "mrktCtg": "KOSDAQ",
            "itmsNm": "파두",
        }
    )

    assert isinstance(record, StockMasterRecord)
    assert record.code == "440110"
    assert record.name_kr == "파두"
    assert record.market == "KOSDAQ"
