from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen


@dataclass(slots=True)
class StockMasterRecord:
    code: str
    name_kr: str
    market: str
    sector: str | None = None
    isin: str | None = None
    dart_corp_code: str | None = None
    security_type: str = "unknown"
    is_common_stock: bool = True
    is_preferred: bool = False
    is_etf: bool = False
    is_etn: bool = False
    is_spac: bool = False


def _normalize_bool_flags(name: str) -> tuple[bool, bool, bool, bool, bool, str]:
    normalized = name.strip()
    upper = normalized.upper()
    is_etf = "ETF" in upper
    is_etn = "ETN" in upper
    is_spac = "스팩" in normalized or "SPAC" in upper
    is_preferred = normalized.endswith("우") or "우선주" in normalized
    is_common_stock = not any((is_etf, is_etn, is_spac, is_preferred))
    security_type = "common_stock" if is_common_stock else "other"
    return is_common_stock, is_preferred, is_etf, is_etn, is_spac, security_type


def _pick(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response")
    if isinstance(response, dict):
        body = response.get("body")
        if isinstance(body, dict):
            items = body.get("items")
            if isinstance(items, dict):
                inner = items.get("item")
                if isinstance(inner, list):
                    return inner
                if isinstance(inner, dict):
                    return [inner]
            if isinstance(items, list):
                return items
    if isinstance(payload.get("items"), list):
        return payload["items"]
    if isinstance(payload.get("data"), list):
        return payload["data"]
    return []


def _to_record(item: dict[str, Any]) -> StockMasterRecord | None:
    code = _pick(item, "srtnCd", "itmsShrtnCd", "code")
    name_kr = _pick(item, "itmsNm", "isinCdNm", "name")
    market = _pick(item, "mrktCtg", "mrktCtgNm", "market")
    isin = _pick(item, "isinCd", "isin")
    sector = _pick(item, "indutyNm", "sector")

    if not code or not name_kr or not market:
        return None

    is_common_stock, is_preferred, is_etf, is_etn, is_spac, security_type = _normalize_bool_flags(name_kr)
    return StockMasterRecord(
        code=code,
        name_kr=name_kr,
        market=market,
        sector=sector,
        isin=isin,
        security_type=security_type,
        is_common_stock=is_common_stock,
        is_preferred=is_preferred,
        is_etf=is_etf,
        is_etn=is_etn,
        is_spac=is_spac,
    )


def fetch_krx_master_records(
    api_url: str,
    service_key: str,
    base_date: str,
    num_of_rows: int = 5000,
    page_no: int = 1,
    timeout: int = 30,
) -> list[StockMasterRecord]:
    params = {
        "serviceKey": service_key,
        "resultType": "json",
        "basDt": base_date,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    request_url = f"{api_url}?{urlencode(params)}"
    with urlopen(request_url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    records: list[StockMasterRecord] = []
    for item in _extract_items(payload):
        record = _to_record(item)
        if record is not None:
            records.append(record)
    return records
