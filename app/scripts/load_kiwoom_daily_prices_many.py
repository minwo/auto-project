from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from app.collectors.kiwoom_open_api import DailyPriceRecord, fetch_daily_price_records, issue_access_token
from app.postgres_repository import create_postgres_repository
from app.settings import AppSettings, load_settings


@dataclass(slots=True)
class LoadResult:
    code: str
    fetched_rows: int = 0
    upserted_rows: int = 0
    error: str | None = None


@dataclass(slots=True)
class StockCodeMetadata:
    code: str
    name: str | None = None


def _default_base_date() -> str:
    return date.today().strftime("%Y%m%d")


def _normalize_stock_code(raw_code: str) -> str:
    code = raw_code.strip()
    if not code:
        raise ValueError("stock code is empty")
    if code.isdigit() and len(code) <= 6:
        return code.zfill(6)
    if re.fullmatch(r"\d{6}", code):
        return code
    raise ValueError(f"invalid stock code: {raw_code}")


def parse_code_list(value: str) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for raw_code in re.split(r"[\s,]+", value):
        if not raw_code:
            continue
        code = _normalize_stock_code(raw_code)
        if code not in seen:
            codes.append(code)
            seen.add(code)
    return codes


def parse_code_text(text: str) -> list[str]:
    values: list[str] = []
    for line in text.splitlines():
        body = line.split("#", 1)[0].strip()
        if body:
            values.extend(parse_code_list(body))

    codes: list[str] = []
    seen: set[str] = set()
    for code in values:
        if code not in seen:
            codes.append(code)
            seen.add(code)
    return codes


def parse_code_metadata_text(text: str) -> list[StockCodeMetadata]:
    records: list[StockCodeMetadata] = []
    seen: set[str] = set()
    for line in text.splitlines():
        body, _, comment = line.partition("#")
        body = body.strip()
        if not body:
            continue
        codes = parse_code_list(body)
        name = comment.strip() or None
        for code in codes:
            if code in seen:
                continue
            records.append(StockCodeMetadata(code=code, name=name if len(codes) == 1 else None))
            seen.add(code)
    return records


def read_codes_file(path: Path) -> list[str]:
    return parse_code_text(path.read_text(encoding="utf-8"))


def read_code_metadata_file(path: Path) -> list[StockCodeMetadata]:
    return parse_code_metadata_text(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load daily price data for multiple stocks from Kiwoom REST API.")
    parser.add_argument("--codes", help="Comma or whitespace separated stock codes, e.g. 005930,000660")
    parser.add_argument("--codes-file", type=Path, help="Text file containing stock codes. Commas, whitespace, and # comments are allowed.")
    parser.add_argument("--from-master", action="store_true", help="Load codes from stock_master instead of passing them manually.")
    parser.add_argument("--market", action="append", help="Market filter for --from-master. Can be passed multiple times.")
    parser.add_argument("--limit", type=int, help="Maximum number of stock codes to load.")
    parser.add_argument("--date", default=_default_base_date(), help="Base date in YYYYMMDD format")
    parser.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between API calls")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop the run when a stock fails")
    return parser


def _validate_settings(settings: AppSettings) -> None:
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


def _codes_from_args(args: argparse.Namespace, repo) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()

    def add_many(values: list[str]) -> None:
        for code in values:
            if code not in seen:
                codes.append(code)
                seen.add(code)

    if args.codes:
        add_many(parse_code_list(args.codes))
    if args.codes_file:
        add_many(read_codes_file(args.codes_file))
    if args.from_master:
        add_many(repo.fetch_stock_codes_for_price_load(markets=args.market, limit=args.limit))

    if args.limit is not None:
        codes = codes[: args.limit]
    if not codes:
        raise SystemExit("No stock codes to load. Use --codes, --codes-file, or --from-master.")
    return codes


def _fetch_records_for_code(
    *,
    settings: AppSettings,
    client: httpx.Client,
    token: str,
    code: str,
    base_date: str,
) -> list[DailyPriceRecord]:
    return fetch_daily_price_records(
        base_url=settings.kiwoom_base_url or "",
        chart_path=settings.kiwoom_daily_chart_api_path or "",
        app_key=settings.kiwoom_app_key or "",
        secret_key=settings.kiwoom_secret_key or "",
        access_token=token,
        api_id=settings.kiwoom_daily_chart_api_id or "",
        stock_code=code,
        base_date=base_date,
        date_field=settings.kiwoom_daily_chart_date_field or "",
        query_type_field=settings.kiwoom_daily_chart_query_type_field or "",
        query_type=settings.kiwoom_daily_chart_query_type or "",
        adjusted_price_field=settings.kiwoom_daily_chart_adjusted_price_field or "",
        adjusted_price=settings.kiwoom_daily_chart_adjusted_price or "",
        exchange_suffix=settings.kiwoom_exchange_suffix or "",
        client=client,
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    _validate_settings(settings)

    repo = create_postgres_repository(settings.database_url or "")
    codes = _codes_from_args(args, repo)
    print(f"Loading Kiwoom daily prices for {len(codes)} codes on base date {args.date}")

    with httpx.Client(base_url=settings.kiwoom_base_url, timeout=15.0) as client:
        print("Issuing Kiwoom access token ...")
        token = issue_access_token(
            base_url=settings.kiwoom_base_url or "",
            token_path=settings.kiwoom_token_path or "",
            app_key=settings.kiwoom_app_key or "",
            secret_key=settings.kiwoom_secret_key or "",
            client=client,
        )

        results: list[LoadResult] = []
        for index, code in enumerate(codes, start=1):
            try:
                records = _fetch_records_for_code(
                    settings=settings,
                    client=client,
                    token=token.token,
                    code=code,
                    base_date=args.date,
                )
                upserted = repo.upsert_daily_price_records(records)
                results.append(LoadResult(code=code, fetched_rows=len(records), upserted_rows=upserted))
                print(f"[{index}/{len(codes)}] {code}: fetched={len(records)} upserted={upserted}")
            except Exception as exc:
                results.append(LoadResult(code=code, error=str(exc)))
                print(f"[{index}/{len(codes)}] {code}: failed: {exc}")
                if args.stop_on_error:
                    raise
            if args.sleep > 0 and index < len(codes):
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
