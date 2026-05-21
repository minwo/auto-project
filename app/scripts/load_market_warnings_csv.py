from __future__ import annotations

import argparse
from datetime import date

from app.collectors.market_warnings import parse_market_warning_csv
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load daily market warning rows from a CSV file.")
    parser.add_argument("csv_path", help="CSV path. Required columns: code and either --date or trade_date.")
    parser.add_argument("--date", dest="trade_date", help="Apply one trade date to every row in YYYY-MM-DD format.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")

    trade_date = date.fromisoformat(args.trade_date) if args.trade_date else None
    records = parse_market_warning_csv(args.csv_path, trade_date=trade_date)
    repo = create_postgres_repository(settings.database_url)
    inserted = repo.upsert_daily_market_warning_records(records)

    print(f"Parsed market warning rows: {len(records)}")
    print(f"Upserted daily_market_warnings rows: {inserted}")


if __name__ == "__main__":
    main()
