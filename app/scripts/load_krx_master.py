from __future__ import annotations

from datetime import date, timedelta

from app.collectors.krx_master import fetch_krx_master_records
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


def previous_business_day(reference: date | None = None) -> date:
    current = reference or date.today()
    day = current - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def main() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.data_go_kr_service_key:
        raise SystemExit("DATA_GO_KR_SERVICE_KEY is not set.")
    if not settings.krx_master_api_url:
        raise SystemExit("KRX_MASTER_API_URL is not set.")

    base_date = previous_business_day().strftime("%Y%m%d")
    print(f"Fetching KRX master data for {base_date} ...")
    records = fetch_krx_master_records(
        api_url=settings.krx_master_api_url,
        service_key=settings.data_go_kr_service_key,
        base_date=base_date,
    )
    print(f"Fetched {len(records)} records")

    repo = create_postgres_repository(settings.database_url)
    inserted = repo.upsert_stock_master_records(records)
    print(f"Upserted {inserted} stock_master rows")


if __name__ == "__main__":
    main()
