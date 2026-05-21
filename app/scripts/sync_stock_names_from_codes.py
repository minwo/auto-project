from __future__ import annotations

import argparse
from pathlib import Path

from app.postgres_repository import create_postgres_repository
from app.scripts.load_kiwoom_daily_prices_many import read_code_metadata_file
from app.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync stock display names from a code file comment.")
    parser.add_argument("--file", type=Path, default=Path("data/stock_codes.txt"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")

    metadata = read_code_metadata_file(args.file)
    names = [(item.code, item.name) for item in metadata if item.name]
    if not names:
        raise SystemExit(f"No stock names found in {args.file}. Use lines like `005930 # 삼성전자`.")

    repo = create_postgres_repository(settings.database_url)
    updated = repo.update_stock_display_names(names)
    print(f"Read {len(metadata)} code rows from {args.file}")
    print(f"Updated {updated} stock_master names")


if __name__ == "__main__":
    main()
