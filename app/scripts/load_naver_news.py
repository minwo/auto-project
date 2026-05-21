from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from app.collectors.naver_news import NaverNewsRecord, fetch_news_records
from app.postgres_repository import create_postgres_repository
from app.scripts.load_kiwoom_daily_prices_many import (
    StockCodeMetadata,
    parse_code_list,
    read_code_metadata_file,
)
from app.settings import AppSettings, load_settings


@dataclass(slots=True)
class LoadResult:
    code: str
    fetched_rows: int = 0
    upserted_rows: int = 0
    error: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load daily stock news from Naver Search API.")
    parser.add_argument("--date", default=date.today().isoformat(), help="News date in YYYY-MM-DD format")
    parser.add_argument("--codes", help="Comma or whitespace separated stock codes, e.g. 005930,000660")
    parser.add_argument("--codes-file", type=Path, help="Text file containing stock codes. # comments can be used as names.")
    parser.add_argument("--from-master", action="store_true", help="Load codes and names from stock_master.")
    parser.add_argument("--market", action="append", help="Market filter for --from-master. Can be passed multiple times.")
    parser.add_argument("--limit", type=int, help="Maximum number of stock codes to load.")
    parser.add_argument("--display", type=int, default=10, help="Naver results per stock. Max 100.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Seconds to sleep between API calls")
    parser.add_argument("--loose-date", action="store_true", help="Keep results even when pubDate differs from --date.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop the run when a stock fails")
    return parser


def _validate_settings(settings: AppSettings) -> None:
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.naver_client_id or not settings.naver_client_secret:
        raise SystemExit("NAVER_CLIENT_ID or NAVER_CLIENT_SECRET is not set.")
    if not settings.naver_news_api_url:
        raise SystemExit("NAVER_NEWS_API_URL is not set.")


def _manual_targets(args: argparse.Namespace, repo) -> list[StockCodeMetadata]:
    records: list[StockCodeMetadata] = []
    seen: set[str] = set()

    def add(code: str, name: str | None = None) -> None:
        if code in seen:
            return
        records.append(StockCodeMetadata(code=code, name=name))
        seen.add(code)

    if args.codes:
        for code in parse_code_list(args.codes):
            add(code)
    if args.codes_file:
        for record in read_code_metadata_file(args.codes_file):
            add(record.code, record.name)

    if not records:
        return []

    codes = [record.code for record in records]
    name_map = dict(repo.fetch_stock_news_targets(codes=codes))
    resolved = [
        StockCodeMetadata(code=record.code, name=name_map.get(record.code) or record.name or record.code)
        for record in records
    ]
    return resolved[: args.limit] if args.limit is not None else resolved


def _targets_from_args(args: argparse.Namespace, repo) -> list[StockCodeMetadata]:
    if args.from_master:
        targets = [
            StockCodeMetadata(code=code, name=name)
            for code, name in repo.fetch_stock_news_targets(markets=args.market, limit=args.limit)
        ]
        if targets:
            return targets

    targets = _manual_targets(args, repo)
    if not targets:
        raise SystemExit("No stock codes to load. Use --codes, --codes-file, or --from-master.")
    return targets


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    _validate_settings(settings)

    trade_date = date.fromisoformat(args.date)
    repo = create_postgres_repository(settings.database_url or "")
    targets = _targets_from_args(args, repo)
    print(f"Loading Naver news for {len(targets)} codes on {trade_date.isoformat()}")

    results: list[LoadResult] = []
    with httpx.Client(timeout=15.0) as client:
        for index, target in enumerate(targets, start=1):
            try:
                records: list[NaverNewsRecord] = fetch_news_records(
                    client_id=settings.naver_client_id or "",
                    client_secret=settings.naver_client_secret or "",
                    trade_date=trade_date,
                    code=target.code,
                    name=target.name,
                    api_url=settings.naver_news_api_url or "",
                    display=args.display,
                    strict_date=not args.loose_date,
                    client=client,
                )
                upserted = repo.upsert_daily_news_records(records)
                results.append(LoadResult(code=target.code, fetched_rows=len(records), upserted_rows=upserted))
                print(f"[{index}/{len(targets)}] {target.code}: fetched={len(records)} upserted={upserted}")
            except Exception as exc:
                results.append(LoadResult(code=target.code, error=str(exc)))
                print(f"[{index}/{len(targets)}] {target.code}: failed: {exc}")
                if args.stop_on_error:
                    raise
            if args.sleep > 0 and index < len(targets):
                time.sleep(args.sleep)

    succeeded = sum(1 for result in results if result.error is None)
    failed = len(results) - succeeded
    fetched_rows = sum(result.fetched_rows for result in results)
    upserted_rows = sum(result.upserted_rows for result in results)
    print(f"Done. succeeded={succeeded} failed={failed} fetched_rows={fetched_rows} upserted_rows={upserted_rows}")
    if failed:
        failed_codes = ", ".join(result.code for result in results if result.error)
        print(f"Failed codes: {failed_codes}")


if __name__ == "__main__":
    main()
