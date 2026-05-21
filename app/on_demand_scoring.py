from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

import httpx

from app.batch import evaluate_daily_batch_with_surge
from app.collectors.kiwoom_open_api import fetch_daily_price_records, issue_access_token
from app.domain import CandidateEvaluation
from app.repository import select_top_candidates
from app.settings import AppSettings

DEFAULT_ALIAS_FILE = Path("data/stock_aliases.txt")


class OnDemandRepository(Protocol):
    def upsert_daily_price_records(self, records): ...
    def fetch_price_history_for_batch(self, score_date: date, history_limit: int = 25): ...
    def fetch_market_warnings_for_date(self, score_date: date): ...
    def fetch_disclosures_for_date(self, score_date: date): ...
    def fetch_news_for_date(self, score_date: date): ...
    def upsert_daily_scores(self, score_date: date, evaluations: list[CandidateEvaluation]) -> None: ...


def normalize_stock_code(value: str) -> str | None:
    normalized = value.strip()
    if re.fullmatch(r"\d{1,6}", normalized):
        return normalized.zfill(6)
    return None


def resolve_alias_codes(query: str, alias_file: Path = DEFAULT_ALIAS_FILE, limit: int = 5) -> list[str]:
    normalized_query = query.strip().lower()
    if not normalized_query or not alias_file.exists():
        return []

    matches: list[str] = []
    seen: set[str] = set()
    for line in alias_file.read_text(encoding="utf-8").splitlines():
        body, _, comment = line.partition("#")
        code = normalize_stock_code(body)
        name = comment.strip()
        if not code or code in seen:
            continue
        haystack = f"{code} {name}".lower()
        if normalized_query in haystack:
            matches.append(code)
            seen.add(code)
        if len(matches) >= limit:
            break
    return matches


def resolve_search_codes(repo: object, query: str, limit: int = 5) -> list[str]:
    code = normalize_stock_code(query)
    if code:
        return [code]

    alias_codes = resolve_alias_codes(query, limit=limit)
    if alias_codes:
        return alias_codes

    resolver = getattr(repo, "resolve_stock_codes", None)
    if callable(resolver):
        resolved = list(resolver(query, limit=limit))
        if resolved:
            return resolved
    return []


def ensure_alias_master_records(repo: object, query: str) -> None:
    aliases = resolve_alias_codes(query)
    if not aliases:
        return
    updater = getattr(repo, "upsert_manual_stock_records", None)
    if callable(updater):
        updater(read_alias_records())


def read_alias_records(alias_file: Path = DEFAULT_ALIAS_FILE) -> list[tuple[str, str]]:
    if not alias_file.exists():
        return []
    records: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in alias_file.read_text(encoding="utf-8").splitlines():
        body, _, comment = line.partition("#")
        code = normalize_stock_code(body)
        name = comment.strip()
        if not code or not name or code in seen:
            continue
        records.append((code, name))
        seen.add(code)
    return records


def _validate_settings(settings: AppSettings) -> None:
    if not settings.kiwoom_app_key or not settings.kiwoom_secret_key:
        raise RuntimeError("KIWOOM_APP_KEY or KIWOOM_SECRET_KEY is not set.")
    if not settings.kiwoom_base_url or not settings.kiwoom_token_path:
        raise RuntimeError("KIWOOM_BASE_URL or KIWOOM_TOKEN_PATH is not set.")
    if not settings.kiwoom_daily_chart_api_path or not settings.kiwoom_daily_chart_api_id:
        raise RuntimeError("KIWOOM_DAILY_CHART_API_PATH or KIWOOM_DAILY_CHART_API_ID is not set.")
    if not settings.kiwoom_daily_chart_date_field:
        raise RuntimeError("KIWOOM_DAILY_CHART_DATE_FIELD is not set.")


def load_and_score_search_codes(
    *,
    repo: OnDemandRepository,
    settings: AppSettings,
    query: str,
    score_date: date,
    history_limit: int = 90,
    resolve_limit: int = 5,
) -> list[CandidateEvaluation]:
    codes = resolve_search_codes(repo, query, limit=resolve_limit)
    if not codes:
        return []
    ensure_alias_master_records(repo, query)

    _validate_settings(settings)
    base_date = score_date.strftime("%Y%m%d")
    records = []

    with httpx.Client(base_url=settings.kiwoom_base_url, timeout=15.0) as client:
        token = issue_access_token(
            base_url=settings.kiwoom_base_url or "",
            token_path=settings.kiwoom_token_path or "",
            app_key=settings.kiwoom_app_key or "",
            secret_key=settings.kiwoom_secret_key or "",
            client=client,
        )
        for code in codes:
            records.extend(
                fetch_daily_price_records(
                    base_url=settings.kiwoom_base_url or "",
                    chart_path=settings.kiwoom_daily_chart_api_path or "",
                    app_key=settings.kiwoom_app_key or "",
                    secret_key=settings.kiwoom_secret_key or "",
                    access_token=token.token,
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
            )

    if not records:
        return []

    repo.upsert_daily_price_records(records)

    price_rows = repo.fetch_price_history_for_batch(score_date=score_date, history_limit=history_limit)
    warning_rows = repo.fetch_market_warnings_for_date(score_date)
    disclosure_rows = repo.fetch_disclosures_for_date(score_date)
    fetch_news_rows = getattr(repo, "fetch_news_for_date", None)
    news_rows = fetch_news_rows(score_date) if callable(fetch_news_rows) else []
    evaluations = evaluate_daily_batch_with_surge(
        score_date=score_date,
        price_rows=price_rows,
        warning_rows=warning_rows,
        disclosure_rows=disclosure_rows,
        news_rows=news_rows,
        generated_at=datetime.now(timezone.utc),
    )
    requested = set(codes)
    matched_profiles = [evaluation for evaluation in evaluations if evaluation.snapshot.code in requested]
    matched = select_top_candidates(
        matched_profiles,
        min_score=0.0,
        max_per_sector=resolve_limit,
        limit=resolve_limit,
        separate_profiles=True,
    )
    if matched:
        repo.upsert_daily_scores(score_date, matched)
    return sorted(matched, key=lambda item: item.score, reverse=True)
