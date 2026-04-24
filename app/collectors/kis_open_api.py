from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


MARKET_CODE_TO_NAME = {
    "J": "KRX",
    "UN": "KOSPI",
    "Q": "KOSDAQ",
}


@dataclass(slots=True)
class KisAccessToken:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None


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
    source: str = "kis_open_api"
    name_kr: str | None = None
    market: str | None = None
    sector: str | None = None


def _as_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(str(value).replace(",", ""))


def issue_access_token(
    *,
    base_url: str,
    token_path: str,
    app_key: str,
    app_secret: str,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> KisAccessToken:
    request_client = client or httpx.Client(base_url=base_url, timeout=timeout)
    close_client = client is None
    try:
        response = request_client.post(
            token_path,
            json={
                "grant_type": "client_credentials",
                "appkey": app_key,
                "appsecret": app_secret,
            },
            headers={"content-type": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if close_client:
            request_client.close()

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError(f"KIS token response does not include access_token: {payload}")

    expires_in = payload.get("expires_in")
    return KisAccessToken(
        access_token=access_token,
        token_type=payload.get("token_type", "Bearer"),
        expires_in=int(expires_in) if expires_in not in (None, "") else None,
    )


def parse_kis_daily_price_records(
    payload: dict[str, Any],
    *,
    requested_code: str,
    market_code: str,
) -> list[DailyPriceRecord]:
    result_code = str(payload.get("rt_cd", ""))
    if result_code and result_code != "0":
        raise RuntimeError(payload.get("msg1") or f"KIS quote request failed: rt_cd={result_code}")

    summary = payload.get("output1") or {}
    rows = payload.get("output2") or []
    if not isinstance(rows, list):
        raise RuntimeError("KIS daily price response output2 must be a list.")

    name_kr = summary.get("hts_kor_isnm") or summary.get("prdt_name") or None
    sector = summary.get("bstp_kor_isnm") or summary.get("stck_prpr_name") or None
    market = summary.get("rprs_mrkt_kor_name") or MARKET_CODE_TO_NAME.get(market_code, "KRX")

    records: list[DailyPriceRecord] = []
    for row in rows:
        trade_date = row.get("stck_bsop_date")
        if not trade_date:
            continue
        records.append(
            DailyPriceRecord(
                trade_date=date.fromisoformat(
                    f"{trade_date[0:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
                ),
                code=requested_code,
                open_price=_as_float(row.get("stck_oprc")),
                high_price=_as_float(row.get("stck_hgpr")),
                low_price=_as_float(row.get("stck_lwpr")),
                close_price=_as_float(row.get("stck_clpr")),
                volume=_as_float(row.get("acml_vol")),
                turnover=_as_float(row.get("acml_tr_pbmn")),
                name_kr=name_kr,
                market=market,
                sector=sector,
            )
        )
    return records


def fetch_daily_price_records(
    *,
    base_url: str,
    price_path: str,
    app_key: str,
    app_secret: str,
    access_token: str,
    tr_id: str,
    customer_type: str,
    market_code: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    period_code: str = "D",
    adjusted_price_code: str = "1",
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> list[DailyPriceRecord]:
    headers = {
        "authorization": f"Bearer {access_token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": customer_type,
        "accept": "application/json",
        "content-type": "application/json; charset=utf-8",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": market_code,
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": period_code,
        "FID_ORG_ADJ_PRC": adjusted_price_code,
    }

    request_client = client or httpx.Client(base_url=base_url, timeout=timeout)
    close_client = client is None
    try:
        response = request_client.get(price_path, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
    finally:
        if close_client:
            request_client.close()

    return parse_kis_daily_price_records(
        payload,
        requested_code=stock_code,
        market_code=market_code,
    )
