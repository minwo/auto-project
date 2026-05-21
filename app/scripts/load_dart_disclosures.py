from __future__ import annotations

import argparse
from datetime import date

from app.collectors.dart_open_api import fetch_disclosure_records
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load daily disclosures from Open DART.")
    parser.add_argument("--date", default=date.today().isoformat(), help="Disclosure date in YYYY-MM-DD format")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.dart_api_key:
        raise SystemExit("DART_API_KEY is not set.")

    trade_date = date.fromisoformat(args.date)
    print(f"Fetching DART disclosures for {trade_date.isoformat()} ...")
    records = fetch_disclosure_records(api_key=settings.dart_api_key, trade_date=trade_date)
    print(f"Fetched {len(records)} disclosure rows")

    repo = create_postgres_repository(settings.database_url)
    inserted = repo.upsert_daily_disclosure_records(records)
    print(f"Upserted {inserted} daily_disclosures rows")


if __name__ == "__main__":
    main()
