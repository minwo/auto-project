import pytest

from app.price_validation import validate_ohlc


def test_validate_ohlc_accepts_valid_row() -> None:
    validate_ohlc(open_price=146500, high_price=148000, low_price=143500, close_price=146200)


def test_validate_ohlc_rejects_open_outside_range() -> None:
    with pytest.raises(ValueError, match="open 149800"):
        validate_ohlc(open_price=149800, high_price=148000, low_price=143500, close_price=146200)


def test_validate_ohlc_rejects_close_outside_range() -> None:
    with pytest.raises(ValueError, match="close 142000"):
        validate_ohlc(open_price=146500, high_price=148000, low_price=143500, close_price=142000)
