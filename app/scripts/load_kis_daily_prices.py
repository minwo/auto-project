from __future__ import annotations

import argparse
from datetime import date, timedelta

from app.collectors.kis_open_api import fetch_daily_price_records, issue_access_token
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


def _default_start_date() -> str:
    return (date.today() - timedelta(days=30)).strftime("%Y%m%d")


def _default_end_date() -> str:
    return date.today().strftime("%Y%m%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load daily price data from Korea Investment Open API.")
    parser.add_argument("--code", required=True, help="Stock code, e.g. 005930")
    parser.add_argument("--market-code", default="J", help="KIS market division code. Default: J")
    parser.add_argument("--from-date", default=_default_start_date(), help="Start date in YYYYMMDD format")
    parser.add_argument("--to-date", default=_default_end_date(), help="End date in YYYYMMDD format")
    parser.add_argument("--period-code", default="D", help="Period code. Default: D")
    parser.add_argument("--adjusted-price-code", default="1", help="Adjusted price flag. Default: 1")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()

    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.kis_app_key or not settings.kis_app_secret:
        raise SystemExit("KIS_APP_KEY or KIS_APP_SECRET is not set.")
    if not settings.kis_base_url or not settings.kis_token_path:
        raise SystemExit("KIS_BASE_URL or KIS_TOKEN_PATH is not set.")
    if not settings.kis_daily_price_api_path or not settings.kis_daily_price_tr_id:
        raise SystemExit("KIS_DAILY_PRICE_API_PATH or KIS_DAILY_PRICE_TR_ID is not set.")
    if not settings.kis_customer_type:
        raise SystemExit("KIS_CUSTOMER_TYPE is not set.")

    print("Issuing KIS access token ...")
    token = issue_access_token(
        base_url=settings.kis_base_url,
        token_path=settings.kis_token_path,
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
    )
    print("Fetching KIS daily prices ...")
    records = fetch_daily_price_records(
        base_url=settings.kis_base_url,
        price_path=settings.kis_daily_price_api_path,
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        access_token=token.access_token,
        tr_id=settings.kis_daily_price_tr_id,
        customer_type=settings.kis_customer_type,
        market_code=args.market_code,
        stock_code=args.code,
        start_date=args.from_date,
        end_date=args.to_date,
        period_code=args.period_code,
        adjusted_price_code=args.adjusted_price_code,
    )
    print(f"Fetched {len(records)} price rows for {args.code}")

    repo = create_postgres_repository(settings.database_url)
    inserted = repo.upsert_daily_price_records(records)
    print(f"Upserted {inserted} daily_prices rows")


if __name__ == "__main__":
    main()
