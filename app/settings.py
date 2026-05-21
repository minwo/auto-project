from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_KRX_MASTER_API_URL = "https://apis.data.go.kr/1160100/service/GetKrxListedInfoService/getItemInfo"
DEFAULT_KIWOOM_BASE_URL = "https://api.kiwoom.com"
DEFAULT_KIWOOM_TOKEN_PATH = "/oauth2/token"
DEFAULT_KIWOOM_DAILY_CHART_API_PATH = "/api/dostk/chart"
DEFAULT_KIWOOM_DAILY_CHART_API_ID = "ka10081"
DEFAULT_KIWOOM_DAILY_CHART_DATE_FIELD = "base_dt"
DEFAULT_KIWOOM_DAILY_CHART_QUERY_TYPE_FIELD = ""
DEFAULT_KIWOOM_DAILY_CHART_QUERY_TYPE = ""
DEFAULT_KIWOOM_DAILY_CHART_ADJUSTED_PRICE_FIELD = "upd_stkpc_tp"
DEFAULT_KIWOOM_DAILY_CHART_ADJUSTED_PRICE = "1"
DEFAULT_KIWOOM_EXCHANGE_SUFFIX = ""
DEFAULT_KIWOOM_INDEX_DAILY_CHART_API_PATH = "/api/dostk/chart"
DEFAULT_KIWOOM_INDEX_DAILY_CHART_API_ID = "ka20006"
DEFAULT_KIWOOM_INDEX_DAILY_CHART_DATE_FIELD = "base_dt"
DEFAULT_NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"


@dataclass(slots=True)
class AppSettings:
    database_url: str | None
    postgres_admin_url: str | None
    data_go_kr_service_key: str | None
    dart_api_key: str | None
    krx_master_api_url: str | None
    kiwoom_base_url: str | None
    kiwoom_token_path: str | None
    kiwoom_app_key: str | None
    kiwoom_secret_key: str | None
    kiwoom_daily_chart_api_path: str | None
    kiwoom_daily_chart_api_id: str | None
    kiwoom_daily_chart_date_field: str | None
    kiwoom_daily_chart_query_type_field: str | None
    kiwoom_daily_chart_query_type: str | None
    kiwoom_daily_chart_adjusted_price_field: str | None
    kiwoom_daily_chart_adjusted_price: str | None
    kiwoom_exchange_suffix: str | None
    kiwoom_index_daily_chart_api_path: str | None
    kiwoom_index_daily_chart_api_id: str | None
    kiwoom_index_daily_chart_date_field: str | None
    naver_client_id: str | None
    naver_client_secret: str | None
    naver_news_api_url: str | None

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


@dataclass(slots=True)
class Settings:
    use_database: bool = False
    database_url: str | None = None


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
        dart_api_key=os.getenv("DART_API_KEY") or None,
        krx_master_api_url=os.getenv("KRX_MASTER_API_URL") or DEFAULT_KRX_MASTER_API_URL,
        kiwoom_base_url=os.getenv("KIWOOM_BASE_URL") or DEFAULT_KIWOOM_BASE_URL,
        kiwoom_token_path=os.getenv("KIWOOM_TOKEN_PATH") or DEFAULT_KIWOOM_TOKEN_PATH,
        kiwoom_app_key=os.getenv("KIWOOM_APP_KEY") or None,
        kiwoom_secret_key=os.getenv("KIWOOM_SECRET_KEY") or None,
        kiwoom_daily_chart_api_path=os.getenv("KIWOOM_DAILY_CHART_API_PATH") or DEFAULT_KIWOOM_DAILY_CHART_API_PATH,
        kiwoom_daily_chart_api_id=os.getenv("KIWOOM_DAILY_CHART_API_ID") or DEFAULT_KIWOOM_DAILY_CHART_API_ID,
        kiwoom_daily_chart_date_field=os.getenv("KIWOOM_DAILY_CHART_DATE_FIELD") or DEFAULT_KIWOOM_DAILY_CHART_DATE_FIELD,
        kiwoom_daily_chart_query_type_field=os.getenv("KIWOOM_DAILY_CHART_QUERY_TYPE_FIELD")
        or DEFAULT_KIWOOM_DAILY_CHART_QUERY_TYPE_FIELD,
        kiwoom_daily_chart_query_type=os.getenv("KIWOOM_DAILY_CHART_QUERY_TYPE") or DEFAULT_KIWOOM_DAILY_CHART_QUERY_TYPE,
        kiwoom_daily_chart_adjusted_price_field=os.getenv("KIWOOM_DAILY_CHART_ADJUSTED_PRICE_FIELD")
        or DEFAULT_KIWOOM_DAILY_CHART_ADJUSTED_PRICE_FIELD,
        kiwoom_daily_chart_adjusted_price=os.getenv("KIWOOM_DAILY_CHART_ADJUSTED_PRICE")
        or DEFAULT_KIWOOM_DAILY_CHART_ADJUSTED_PRICE,
        kiwoom_exchange_suffix=os.getenv("KIWOOM_EXCHANGE_SUFFIX") or DEFAULT_KIWOOM_EXCHANGE_SUFFIX,
        kiwoom_index_daily_chart_api_path=os.getenv("KIWOOM_INDEX_DAILY_CHART_API_PATH")
        or DEFAULT_KIWOOM_INDEX_DAILY_CHART_API_PATH,
        kiwoom_index_daily_chart_api_id=os.getenv("KIWOOM_INDEX_DAILY_CHART_API_ID")
        or DEFAULT_KIWOOM_INDEX_DAILY_CHART_API_ID,
        kiwoom_index_daily_chart_date_field=os.getenv("KIWOOM_INDEX_DAILY_CHART_DATE_FIELD")
        or DEFAULT_KIWOOM_INDEX_DAILY_CHART_DATE_FIELD,
        naver_client_id=os.getenv("NAVER_CLIENT_ID") or None,
        naver_client_secret=os.getenv("NAVER_CLIENT_SECRET") or None,
        naver_news_api_url=os.getenv("NAVER_NEWS_API_URL") or DEFAULT_NAVER_NEWS_API_URL,
    )
