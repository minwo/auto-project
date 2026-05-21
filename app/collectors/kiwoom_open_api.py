from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.price_validation import validate_ohlc


@dataclass(slots=True)
class KiwoomAccessToken:
    token: str
    token_type: str = "Bearer"
    expires_dt: str | None = None


@dataclass(slots=True)
class DailyPriceRecord:
    trade_date: date
    code: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    turnover: float
    source: str = "kiwoom_open_api"
    name_kr: str | None = None
    market: str | None = None
    sector: str | None = None


def _as_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(str(value).replace(",", ""))


def _normalize_turnover(turnover: float) -> float:
    # Kiwoom chart responses return turnover in million KRW units for daily chart queries.
    if turnover <= 0:
        return 0.0
    return turnover * 1_000_000.0


def _normalize_index_price(value: Any) -> float:
    # Kiwoom index chart values are returned as integer strings with 2 implied decimal places.
    return abs(_as_float(value)) / 100.0


def _pick_first(payload: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]
    return None


def _clean_error_message(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).replace("\x00", "").strip()


def _format_kiwoom_error(payload: dict[str, Any], default: str) -> str:
    message = _clean_error_message(payload.get("return_msg"))
    return_code = payload.get("return_code")
    has_error_code = return_code not in (None, "", 0, "0")
    if message and has_error_code:
        return f"Kiwoom API error {return_code}: {message}"
    if message:
        return message
    return default


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in [
        "data",
        "items",
        "output",
        "list",
        "data_list",
        "chart_data",
        "stk_min_pole_chart_qry",
        "stk_day_pole_chart_qry",
        "stk_dt_pole_chart_qry",
        "inds_dt_pole_qry",
    ]:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if all(key in payload for key in ["dt", "open_pric", "high_pric", "low_pric", "close_pric"]):
        return [payload]
    return []


def issue_access_token(
    *,
    base_url: str,
    token_path: str,
    app_key: str,
    secret_key: str,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> KiwoomAccessToken:
    request_client = client or httpx.Client(base_url=base_url, timeout=timeout)
    close_client = client is None
    try:
        response = request_client.post(
            token_path,
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "secretkey": secret_key,
            },
            headers={"content-type": "application/json;charset=UTF-8"},
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if close_client:
            request_client.close()

    if int(payload.get("return_code", 0)) != 0:
        raise RuntimeError(_format_kiwoom_error(payload, f"Kiwoom token request failed: {payload}"))

    token = payload.get("token")
    if not token:
        raise RuntimeError(f"Kiwoom token response does not include token: {payload}")

    token_type = payload.get("token_type", "bearer")
    return KiwoomAccessToken(
        token=token,
        token_type=token_type.capitalize() if token_type.islower() else token_type,
        expires_dt=payload.get("expires_dt"),
    )


def parse_kiwoom_daily_price_records(
    payload: dict[str, Any],
    *,
    requested_code: str,
) -> list[DailyPriceRecord]:
    return_code = payload.get("return_code")
    if return_code not in (None, 0, "0"):
        raise RuntimeError(_format_kiwoom_error(payload, f"Kiwoom chart request failed: return_code={return_code}"))

    rows = _extract_rows(payload)
    if not rows:
        return []

    name_kr = _pick_first(payload, ["stk_nm", "stock_name", "name", "stk_name"])
    records: list[DailyPriceRecord] = []

    for row in rows:
        trade_date = _pick_first(row, ["dt", "date", "trde_dt", "stck_bsop_date"])
        if not trade_date:
            continue
        close_price = _as_float(_pick_first(row, ["close_pric", "cur_prc", "close_price", "stck_clpr", "close"]))
        volume = _as_float(_pick_first(row, ["trde_qty", "acml_vol", "volume"]))
        turnover = _as_float(
            _pick_first(row, ["trde_prica", "acc_trde_prica", "acml_tr_pbmn", "turnover", "amt"])
        )
        turnover = _normalize_turnover(turnover)
        if turnover <= 0 and close_price > 0 and volume > 0:
            turnover = close_price * volume
        open_price = _as_float(_pick_first(row, ["open_pric", "stck_oprc", "open_price", "open"]))
        high_price = _as_float(_pick_first(row, ["high_pric", "stck_hgpr", "high_price", "high"]))
        low_price = _as_float(_pick_first(row, ["low_pric", "stck_lwpr", "low_price", "low"]))
        validate_ohlc(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            context=f"{requested_code} {trade_date}",
        )

        records.append(
            DailyPriceRecord(
                trade_date=date.fromisoformat(f"{trade_date[0:4]}-{trade_date[4:6]}-{trade_date[6:8]}"),
                code=requested_code,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                turnover=turnover,
                name_kr=name_kr,
            )
        )
    return records


def fetch_daily_price_records(
    *,
    base_url: str,
    chart_path: str,
    app_key: str,
    secret_key: str,
    access_token: str,
    api_id: str,
    stock_code: str,
    base_date: str,
    date_field: str,
    query_type_field: str,
    query_type: str,
    adjusted_price_field: str,
    adjusted_price: str,
    exchange_suffix: str = "",
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> list[DailyPriceRecord]:
    headers = {
        "authorization": f"Bearer {access_token}",
        "api-id": api_id,
        "content-type": "application/json;charset=UTF-8",
    }
    body = {
        "stk_cd": f"{stock_code}{exchange_suffix}",
        date_field: base_date,
    }
    if query_type_field:
        body[query_type_field] = query_type
    if adjusted_price_field:
        body[adjusted_price_field] = adjusted_price

    request_client = client or httpx.Client(base_url=base_url, timeout=timeout)
    close_client = client is None
    try:
        response = request_client.post(chart_path, json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
    finally:
        if close_client:
            request_client.close()

    return parse_kiwoom_daily_price_records(payload, requested_code=stock_code)


def parse_kiwoom_index_daily_price_records(
    payload: dict[str, Any],
    *,
    requested_index_code: str,
    output_code: str,
    name_kr: str,
) -> list[DailyPriceRecord]:
    return_code = payload.get("return_code")
    if return_code not in (None, 0, "0"):
        raise RuntimeError(_format_kiwoom_error(payload, f"Kiwoom index chart request failed: return_code={return_code}"))

    rows = _extract_rows(payload)
    if not rows:
        return []

    records: list[DailyPriceRecord] = []
    for row in rows:
        trade_date = _pick_first(row, ["dt", "date"])
        if not trade_date:
            continue
        close_price = _normalize_index_price(_pick_first(row, ["cur_prc", "close_pric", "close"]))
        open_price = _normalize_index_price(_pick_first(row, ["open_pric", "open"]))
        high_price = _normalize_index_price(_pick_first(row, ["high_pric", "high"]))
        low_price = _normalize_index_price(_pick_first(row, ["low_pric", "low"]))
        volume = _as_float(_pick_first(row, ["trde_qty", "acc_trde_qty", "volume"]))
        turnover = _normalize_turnover(_as_float(_pick_first(row, ["trde_prica", "acc_trde_prica", "turnover"])))
        validate_ohlc(
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            context=f"{requested_index_code} {trade_date}",
        )
        records.append(
            DailyPriceRecord(
                trade_date=date.fromisoformat(f"{trade_date[0:4]}-{trade_date[4:6]}-{trade_date[6:8]}"),
                code=output_code,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                turnover=turnover,
                source="kiwoom_index_open_api",
                name_kr=name_kr,
                market="INDEX",
                sector="INDEX",
            )
        )
    return records


def fetch_index_daily_price_records(
    *,
    base_url: str,
    chart_path: str,
    access_token: str,
    api_id: str,
    index_code: str,
    output_code: str,
    name_kr: str,
    base_date: str,
    date_field: str,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> list[DailyPriceRecord]:
    headers = {
        "authorization": f"Bearer {access_token}",
        "api-id": api_id,
        "content-type": "application/json;charset=UTF-8",
    }
    body = {
        "inds_cd": index_code,
        date_field: base_date,
    }

    request_client = client or httpx.Client(base_url=base_url, timeout=timeout)
    close_client = client is None
    try:
        response = request_client.post(chart_path, json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
    finally:
        if close_client:
            request_client.close()

    return parse_kiwoom_index_daily_price_records(
        payload,
        requested_index_code=index_code,
        output_code=output_code,
        name_kr=name_kr,
    )
