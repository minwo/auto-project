from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_KRX_MASTER_API_URL = "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo"
DEFAULT_KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
DEFAULT_KIS_TOKEN_PATH = "/oauth2/tokenP"
DEFAULT_KIS_DAILY_PRICE_API_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
DEFAULT_KIS_DAILY_PRICE_TR_ID = "FHKST03010100"
DEFAULT_KIS_CUSTOMER_TYPE = "P"


@dataclass(slots=True)
class AppSettings:
    database_url: str | None
    postgres_admin_url: str | None
    data_go_kr_service_key: str | None
    krx_master_api_url: str | None
    kis_base_url: str | None
    kis_token_path: str | None
    kis_app_key: str | None
    kis_app_secret: str | None
    kis_daily_price_api_path: str | None
    kis_daily_price_tr_id: str | None
    kis_customer_type: str | None

    @property
    def use_database(self) -> bool:
        return bool(self.database_url)

    @property
    def database_name(self) -> str | None:
        if not self.database_url:
            return None
        parsed = urlparse(self.database_url)
        name = parsed.path.lstrip("/")
        return name or None


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_settings() -> AppSettings:
    load_env_file()
    return AppSettings(
        database_url=os.getenv("DATABASE_URL") or None,
        postgres_admin_url=os.getenv("POSTGRES_ADMIN_URL") or None,
        data_go_kr_service_key=os.getenv("DATA_GO_KR_SERVICE_KEY") or None,
        krx_master_api_url=os.getenv("KRX_MASTER_API_URL") or DEFAULT_KRX_MASTER_API_URL,
        kis_base_url=os.getenv("KIS_BASE_URL") or DEFAULT_KIS_BASE_URL,
        kis_token_path=os.getenv("KIS_TOKEN_PATH") or DEFAULT_KIS_TOKEN_PATH,
        kis_app_key=os.getenv("KIS_APP_KEY") or None,
        kis_app_secret=os.getenv("KIS_APP_SECRET") or None,
        kis_daily_price_api_path=os.getenv("KIS_DAILY_PRICE_API_PATH") or DEFAULT_KIS_DAILY_PRICE_API_PATH,
        kis_daily_price_tr_id=os.getenv("KIS_DAILY_PRICE_TR_ID") or DEFAULT_KIS_DAILY_PRICE_TR_ID,
        kis_customer_type=os.getenv("KIS_CUSTOMER_TYPE") or DEFAULT_KIS_CUSTOMER_TYPE,
    )
