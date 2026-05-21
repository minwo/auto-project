from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


TRUE_VALUES = {"1", "true", "t", "yes", "y", "예", "네", "중", "해당"}


@dataclass(slots=True)
class MarketWarningRecord:
    trade_date: date
    code: str
    warning_type: str | None
    warning_level: str | None
    is_halted: bool
    is_under_management: bool
    source_url: str | None = None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _bool(value: str | None) -> bool:
    cleaned = _clean(value)
    return bool(cleaned and cleaned.lower() in TRUE_VALUES)


def _normalize_level(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    mapping = {
        "투자주의": "attention",
        "주의": "attention",
        "attention": "attention",
        "투자경고": "warning",
        "경고": "warning",
        "warning": "warning",
        "투자위험": "danger",
        "위험": "danger",
        "danger": "danger",
    }
    return mapping.get(lowered, lowered)


def parse_market_warning_rows(
    rows: list[dict[str, str | None]],
    *,
    trade_date: date | None = None,
) -> list[MarketWarningRecord]:
    records: list[MarketWarningRecord] = []
    for row in rows:
        code = _clean(row.get("code") or row.get("종목코드"))
        row_date = _clean(row.get("trade_date") or row.get("기준일"))
        effective_date = trade_date or (date.fromisoformat(row_date) if row_date else None)
        if not code or effective_date is None:
            continue
        records.append(
            MarketWarningRecord(
                trade_date=effective_date,
                code=code.zfill(6) if code.isdigit() else code,
                warning_type=_clean(row.get("warning_type") or row.get("경보유형")),
                warning_level=_normalize_level(row.get("warning_level") or row.get("경보수준")),
                is_halted=_bool(row.get("is_halted") or row.get("거래정지")),
                is_under_management=_bool(row.get("is_under_management") or row.get("관리종목")),
                source_url=_clean(row.get("source_url") or row.get("출처")),
            )
        )
    return records


def parse_market_warning_csv(path: str | Path, *, trade_date: date | None = None) -> list[MarketWarningRecord]:
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        return parse_market_warning_rows(list(reader), trade_date=trade_date)
