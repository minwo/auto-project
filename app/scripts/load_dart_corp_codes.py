from __future__ import annotations

from app.collectors.dart_open_api import fetch_corp_code_records
from app.postgres_repository import create_postgres_repository
from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.dart_api_key:
        raise SystemExit("DART_API_KEY is not set.")

    print("Fetching DART corp code mapping ...")
    records = fetch_corp_code_records(api_key=settings.dart_api_key)
    listed_records = [record for record in records if record.stock_code]
    print(f"Fetched {len(records)} corp code rows, listed rows={len(listed_records)}")

    repo = create_postgres_repository(settings.database_url)
    matched = repo.update_dart_corp_codes(listed_records)
    print(f"Updated dart_corp_code for {matched} stock_master rows")


if __name__ == "__main__":
    main()
