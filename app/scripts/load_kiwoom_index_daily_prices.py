from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date

import httpx

from app.collectors.kiwoom_open_api import DailyPriceRecord, fetch_index_daily_price_records, issue_access_token
from app.postgres_repository import create_postgres_repository
from app.settings import AppSettings, load_settings


@dataclass(slots=True)
class IndexTarget:
    kiwoom_code: str
    output_code: str
    name_kr: str


DEFAULT_INDEX_TARGETS = [
    IndexTarget(kiwoom_code="001", output_code="KOSPI", name_kr="KOSPI"),
    IndexTarget(kiwoom_code="101", output_code="KOSDAQ", name_kr="KOSDAQ"),
    IndexTarget(kiwoom_code="201", output_code="KOSPI200", name_kr="KOSPI200"),
]


def _default_base_date() -> str:
    return date.today().strftime("%Y%m%d")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load KOSPI/KOSDAQ index daily chart data from Kiwoom REST API.")
    parser.add_argument("--date", default=_default_base_date(), help="Base date in YYYYMMDD format")
    parser.add_argument(
        "--index",
        action="append",
        choices=[target.output_code for target in DEFAULT_INDEX_TARGETS],
        help="Index to load. Defaults to KOSPI, KOSDAQ, and KOSPI200.",
    )
    return parser


def _validate_settings(settings: AppSettings) -> None:
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set.")
    if not settings.kiwoom_app_key or not settings.kiwoom_secret_key:
        raise SystemExit("KIWOOM_APP_KEY or KIWOOM_SECRET_KEY is not set.")
    if not settings.kiwoom_base_url or not settings.kiwoom_token_path:
        raise SystemExit("KIWOOM_BASE_URL or KIWOOM_TOKEN_PATH is not set.")
    if not settings.kiwoom_index_daily_chart_api_path or not settings.kiwoom_index_daily_chart_api_id:
        raise SystemExit("KIWOOM_INDEX_DAILY_CHART_API_PATH or KIWOOM_INDEX_DAILY_CHART_API_ID is not set.")
    if not settings.kiwoom_index_daily_chart_date_field:
        raise SystemExit("KIWOOM_INDEX_DAILY_CHART_DATE_FIELD is not set.")


def _select_targets(values: list[str] | None) -> list[IndexTarget]:
    if not values:
        return DEFAULT_INDEX_TARGETS
    selected = set(values)
    return [target for target in DEFAULT_INDEX_TARGETS if target.output_code in selected]


def _fetch_records_for_target(
    *,
    settings: AppSettings,
    client: httpx.Client,
    token: str,
    target: IndexTarget,
    base_date: str,
) -> list[DailyPriceRecord]:
    return fetch_index_daily_price_records(
        base_url=settings.kiwoom_base_url or "",
        chart_path=settings.kiwoom_index_daily_chart_api_path or "",
        access_token=token,
        api_id=settings.kiwoom_index_daily_chart_api_id or "",
        index_code=target.kiwoom_code,
        output_code=target.output_code,
        name_kr=target.name_kr,
        base_date=base_date,
        date_field=settings.kiwoom_index_daily_chart_date_field or "",
        client=client,
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    _validate_settings(settings)

    repo = create_postgres_repository(settings.database_url or "")
    targets = _select_targets(args.index)
    print(f"Loading Kiwoom index daily prices for {len(targets)} indices on base date {args.date}")

    with httpx.Client(base_url=settings.kiwoom_base_url, timeout=15.0) as client:
        print("Issuing Kiwoom access token ...")
        token = issue_access_token(
            base_url=settings.kiwoom_base_url or "",
            token_path=settings.kiwoom_token_path or "",
            app_key=settings.kiwoom_app_key or "",
            secret_key=settings.kiwoom_secret_key or "",
            client=client,
        )

        fetched_rows = 0
        upserted_rows = 0
        for target in targets:
            records = _fetch_records_for_target(
                settings=settings,
                client=client,
                token=token.token,
                target=target,
                base_date=args.date,
            )
            upserted = repo.upsert_daily_price_records(records)
            fetched_rows += len(records)
            upserted_rows += upserted
            print(f"{target.output_code}: fetched={len(records)} upserted={upserted}")

    print(f"Done. fetched_rows={fetched_rows} upserted_rows={upserted_rows}")


if __name__ == "__main__":
    main()
