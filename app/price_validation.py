from __future__ import annotations


def validate_ohlc(
    *,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    context: str = "price row",
) -> None:
    values = {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }
    invalid = [name for name, value in values.items() if value < 0]
    if invalid:
        raise ValueError(f"Invalid OHLC for {context}: negative {', '.join(invalid)}")
    if high_price < low_price:
        raise ValueError(f"Invalid OHLC for {context}: high {high_price} is below low {low_price}")
    if open_price > 0 and not low_price <= open_price <= high_price:
        raise ValueError(
            f"Invalid OHLC for {context}: open {open_price} is outside low/high {low_price}/{high_price}"
        )
    if close_price > 0 and not low_price <= close_price <= high_price:
        raise ValueError(
            f"Invalid OHLC for {context}: close {close_price} is outside low/high {low_price}/{high_price}"
        )
