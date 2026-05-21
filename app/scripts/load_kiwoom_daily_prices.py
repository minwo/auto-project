from __future__ import annotations

import argparse
from datetime import date

from app.collectors.kiwoom_open_api import fetch_daily_price_records, issue_access_token
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


def _default_base_date() -> str:
    return date.today().strftime("%Y%m%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load daily price data from Kiwoom REST API.")
    parser.add_argument("--code", required=True, help="Stock code, e.g. 005930")
    parser.add_argument("--date", default=_default_base_date(), help="Base date in YYYYMMDD format")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()

    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.kiwoom_app_key or not settings.kiwoom_secret_key:
        raise SystemExit("KIWOOM_APP_KEY or KIWOOM_SECRET_KEY is not set.")
    if not settings.kiwoom_base_url or not settings.kiwoom_token_path:
        raise SystemExit("KIWOOM_BASE_URL or KIWOOM_TOKEN_PATH is not set.")
    if not settings.kiwoom_daily_chart_api_path or not settings.kiwoom_daily_chart_api_id:
        raise SystemExit("KIWOOM_DAILY_CHART_API_PATH or KIWOOM_DAILY_CHART_API_ID is not set.")
    if not settings.kiwoom_daily_chart_date_field:
        raise SystemExit("KIWOOM_DAILY_CHART_DATE_FIELD is not set.")

    print("Issuing Kiwoom access token ...")
    token = issue_access_token(
        base_url=settings.kiwoom_base_url,
        token_path=settings.kiwoom_token_path,
        app_key=settings.kiwoom_app_key,
        secret_key=settings.kiwoom_secret_key,
    )
    print("Fetching Kiwoom daily prices ...")
    records = fetch_daily_price_records(
        base_url=settings.kiwoom_base_url,
        chart_path=settings.kiwoom_daily_chart_api_path,
        app_key=settings.kiwoom_app_key,
        secret_key=settings.kiwoom_secret_key,
        access_token=token.token,
        api_id=settings.kiwoom_daily_chart_api_id,
        stock_code=args.code,
        base_date=args.date,
        date_field=settings.kiwoom_daily_chart_date_field,
        query_type_field=settings.kiwoom_daily_chart_query_type_field or "",
        query_type=settings.kiwoom_daily_chart_query_type or "",
        adjusted_price_field=settings.kiwoom_daily_chart_adjusted_price_field or "",
        adjusted_price=settings.kiwoom_daily_chart_adjusted_price or "",
        exchange_suffix=settings.kiwoom_exchange_suffix or "",
    )
    print(f"Fetched {len(records)} price rows for {args.code}")

    repo = create_postgres_repository(settings.database_url)
    inserted = repo.upsert_daily_price_records(records)
    print(f"Upserted {inserted} daily_prices rows")


if __name__ == "__main__":
    main()
